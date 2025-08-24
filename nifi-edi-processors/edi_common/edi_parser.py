import logging
import copy
import re
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from edi_schema_models import ImplementationGuideSchema, StructureLoop, StructureSegment, StructureChild
from cdm import CdmInterchange, CdmFunctionalGroup, CdmTransaction, CdmLoop, CdmSegment, CdmElement, CdmValidationError

logger = logging.getLogger(__name__)

# --- Validation Helpers ---
def _validate_data_type(value: str, data_type: str) -> bool:
    if data_type == 'Composite':
        return True
    if data_type in ['AN', 'ID']:
        return True
    if data_type in ('N0', 'N1', 'N2', 'R'):
        if not value: return True
        try:
            float(value)
            return True
        except ValueError:
            return False
    if data_type in ('DT', 'TM'):
        return True
    return False

def _validate_format(value: str, data_format: str) -> bool:
    if not value: return True
    if data_format == 'CCYYMMDD':
        if not (len(value) == 8 and value.isdigit()): return False
        try:
            datetime.strptime(value, '%Y%m%d')
            return True
        except ValueError:
            return False
    if data_format == 'HHMM':
        if not (len(value) == 4 and value.isdigit()): return False
        return 0 <= int(value[:2]) <= 23 and 0 <= int(value[2:]) <= 59
    return True

def get_guide_version_from_edi(edi_string: str) -> Optional[str]:
    element_delimiter = '*'
    segment_delimiter = '~'
    clean_edi = edi_string.strip()
    if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
        element_delimiter = clean_edi[103]
        segment_delimiter = clean_edi[105]
    if segment_delimiter in ('\r', '\n'):
        edi_for_splitting = clean_edi.replace('\r\n', '\n').replace('\r', '\n')
    else:
        edi_for_splitting = clean_edi
    for segment in edi_for_splitting.split(segment_delimiter):
        clean_segment = segment.strip()
        if clean_segment.startswith("GS" + element_delimiter):
            parts = clean_segment.split(element_delimiter)
            if len(parts) > 8: return parts[8]
    return None

def _get_effective_definition(base_def: Dict[str, Any], context_def: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not context_def:
        return base_def

    effective = copy.deepcopy(base_def)
    context_elements = context_def.get("elements", {})
    if not context_elements:
        return effective

    for i, base_el in enumerate(effective.get("elements", [])):
        el_xid = base_el.get("xid")
        if el_xid in context_elements:
            overrides = context_elements[el_xid]

            if 'sub_elements' in overrides and 'sub_elements' in base_el:
                base_sub_elements = base_el['sub_elements']
                override_sub_elements = overrides['sub_elements']

                if isinstance(base_sub_elements, list) and isinstance(override_sub_elements, dict):
                    for j, base_sub_el in enumerate(base_sub_elements):
                        sub_el_xid = base_sub_el.get("xid")
                        if sub_el_xid in override_sub_elements:
                            base_sub_elements[j].update(override_sub_elements[sub_el_xid])

                del overrides['sub_elements']

            for key, value in overrides.items():
                if value is not None:
                    effective["elements"][i][key] = value
    return effective

class SegmentValidator:
    def __init__(self, schema: ImplementationGuideSchema, component_separator: str):
        self.schema = schema
        self.component_separator = component_separator

    def validate(self, segment: CdmSegment, context_id: Optional[str] = None) -> List[CdmValidationError]:
        logger.debug(f"      --- Validating Segment: '{segment.raw_segment}' (Context: {context_id or 'Base Definition'}) ---")
        
        errors: List[CdmValidationError] = []
        base_def_model = self.schema.segmentDefinitions.get(segment.segment_id)
        if not base_def_model:
            logger.warning(f"[FAIL] Base definition for '{segment.segment_id}' not found in schema. (Line: {segment.line_number})")
            return [CdmValidationError(message=f"Base definition for segment '{segment.segment_id}' not found in schema.")]
        
        base_def = base_def_model.model_dump(exclude_none=True)
        context_def_model = self.schema.contextualDefinitions.get(context_id) if context_id else None
        context_def = context_def_model.model_dump(exclude_none=True) if context_def_model else None
        
        effective_def = _get_effective_definition(base_def, context_def)
        elements_in_data = {el.position: el.value for el in segment.elements}

        for element_def in effective_def.get("elements", []):
            el_pos = element_def.get('seq')
            if not el_pos: continue
            value_in_data = elements_in_data.get(el_pos, "")
            errors.extend(self._validate_element_recursively(element_def, value_in_data))
        
        errors.extend(self._validate_syntax_rules(segment, effective_def))
        return errors

    def _validate_syntax_rules(self, segment: CdmSegment, effective_def: Dict[str, Any]) -> List[CdmValidationError]:
        errors: List[CdmValidationError] = []
        rules = effective_def.get("rules", [])
        if not rules: return errors
        
        logger.debug(f"        Syntax Rules: Found {len(rules)} rules for segment '{segment.segment_id}'.")
        for rule in rules:
            rule_id = rule.get('ruleId', 'UnknownRule')
            logger.debug(f"          -> Evaluating Rule: {rule_id}")
            conditions_met = self._evaluate_conditions(segment, rule.get("conditions", {}))
            if conditions_met:
                logger.debug(f"             - Conditions MET. Executing assertions.")
                for assertion in rule.get("then", []):
                    errors.extend(self._execute_assertion(segment, assertion, rule_id))
            else:
                logger.debug(f"             - Conditions NOT MET. Skipping assertions.")
        return errors

    def _evaluate_conditions(self, segment: CdmSegment, conditions: Dict[str, Any]) -> bool:
        if "ALL_OF" in conditions:
            return all(self._evaluate_condition_clause(segment, clause) for clause in conditions["ALL_OF"])
        if "ANY_OF" in conditions:
            return any(self._evaluate_condition_clause(segment, clause) for clause in conditions["ANY_OF"])
        return True

    def _evaluate_condition_clause(self, segment: CdmSegment, clause: Dict[str, Any]) -> bool:
        element_id = clause["element"]
        pos = int(re.sub(r'\D', '', element_id))
        value = segment.get_element(pos) or ""
        op = clause["operator"]
        
        result = False
        if op == "IS_PRESENT": result = value.strip() != ""
        if op == "IS_NOT_PRESENT": result = value.strip() == ""
        if op == "IS": result = value == clause["value"]
        if op == "IS_NOT": result = value != clause["value"]

        logger.debug(f"               - Condition: '{element_id}' ({value}) {op} '{clause.get('value', '')}' -> {'PASS' if result else 'FAIL'}")
        return result

    def _execute_assertion(self, segment: CdmSegment, assertion: Dict[str, Any], rule_id: str) -> List[CdmValidationError]:
        errors: List[CdmValidationError] = []
        assertion_type = assertion["assertion"]
        assertion_failed = False
        log_detail = ""

        if assertion_type == "MUST_BE_PRESENT":
            element_id = assertion["element"]
            pos = int(re.sub(r'\D', '', element_id))
            value = segment.get_element(pos) or ""
            if not (value and value.strip()): assertion_failed = True
            log_detail = f"Asserting {element_id} MUST BE PRESENT. Data='{value}'"
        
        elif assertion_type == "MUST_HAVE_LENGTH":
            element_id = assertion["element"]
            pos = int(re.sub(r'\D', '', element_id))
            value = segment.get_element(pos) or ""
            expected_length = assertion["value"]
            if len(value) != expected_length: assertion_failed = True
            log_detail = f"Asserting {element_id} MUST HAVE LENGTH {expected_length}. Data='{value}' (length={len(value)})"

        elif assertion_type == "ANY_OF_MUST_BE_PRESENT":
            element_ids = assertion["elements"]
            positions = [int(re.sub(r'\D', '', el_id)) for el_id in element_ids]
            if not any(segment.get_element(pos) for pos in positions): assertion_failed = True
            log_detail = f"Asserting ANY OF {', '.join(element_ids)} MUST BE PRESENT."

        if assertion_failed:
            errors.append(CdmValidationError(message=f"Syntax Rule Failed ({rule_id}): {log_detail}"))
            logger.debug(f"               - Assertion FAILED: {log_detail}")
        else:
            logger.debug(f"               - Assertion PASSED: {log_detail}")

        return errors

    def _validate_element_recursively(self, element_def: Dict[str, Any], value: str, parent_xid: Optional[str] = None) -> List[CdmValidationError]:
        errors: List[CdmValidationError] = []
        xid = element_def.get("xid")
        full_xid = f"{parent_xid}-{xid}" if parent_xid else xid
        usage = element_def.get("usage", "S")
        is_present = value != ""
        is_identifier = element_def.get("is_identifier", False)

        log_line_intro = f"        Validating {full_xid} (Usage: {usage}, ID: {is_identifier}): Data='{value}'"

        if usage == 'R' and not is_present:
            err_msg = f"Required element '{full_xid}' is missing."
            logger.debug(f"{log_line_intro} -> [FAIL] {err_msg}")
            errors.append(CdmValidationError(message=err_msg, element_xid=full_xid, is_identifier_error=is_identifier))
            return errors

        if usage == 'N' and is_present:
            err_msg = f"Element '{full_xid}' is Not Used and should not contain data."
            logger.debug(f"{log_line_intro} -> [FAIL] {err_msg}")
            errors.append(CdmValidationError(message=err_msg, element_xid=full_xid, is_identifier_error=is_identifier))

        if not is_present:
            if usage != 'N':
                 logger.debug(f"{log_line_intro} -> [PASS] Optional element is not present.")
            return errors

        data_type = element_def.get('dataType')
        if data_type == 'Composite':
            logger.debug(f"{log_line_intro} -> [INFO] Is Composite. Validating sub-elements.")
            sub_element_values = value.split(self.component_separator)
            sub_element_defs = element_def.get('sub_elements', [])

            if isinstance(sub_element_defs, list):
                for sub_def in sub_element_defs:
                    sub_pos = sub_def.get('seq')
                    if not sub_pos: continue
                    sub_value = sub_element_values[sub_pos - 1] if sub_pos - 1 < len(sub_element_values) else ""
                    errors.extend(self._validate_element_recursively(sub_def, sub_value, parent_xid=full_xid))
            return errors

        validation_passed_count = 0
        
        min_len, max_len = element_def.get('minLength'), element_def.get('maxLength')
        if min_len is not None and len(value) < min_len:
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value is shorter than min length {min_len}.", element_xid=full_xid, is_identifier_error=is_identifier))
        else:
            validation_passed_count += 1
        if max_len is not None and len(value) > max_len:
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value is longer than max length {max_len}.", element_xid=full_xid, is_identifier_error=is_identifier))
        else:
            validation_passed_count += 1

        if data_type and not _validate_data_type(value, data_type):
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value does not match expected data type '{data_type}'.", element_xid=full_xid, is_identifier_error=is_identifier))
        else:
            validation_passed_count += 1
        data_format = element_def.get('format')
        if data_format and not _validate_format(value, data_format):
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value does not match expected format '{data_format}'.", element_xid=full_xid, is_identifier_error=is_identifier))
        else:
            validation_passed_count += 1

        if "valid_codes" in element_def and element_def["valid_codes"]:
            allowed_codes = {str(c['code']) for c in element_def["valid_codes"]}
            if value not in allowed_codes:
                errors.append(CdmValidationError(message=f"Element '{full_xid}': Invalid code value. Allowed: {', '.join(sorted(list(allowed_codes)))}.", element_xid=full_xid, is_identifier_error=is_identifier))
            else:
                validation_passed_count += 1
        else:
             validation_passed_count += 1

        if validation_passed_count == 5:
            logger.debug(f"{log_line_intro} -> [PASS]")
        else:
            logger.debug(f"{log_line_intro} -> [FAIL] One or more validation checks failed. Errors: {[e.message for e in errors]}")

        return errors

class EdiParser:
    def __init__(self, edi_string: str, schema: ImplementationGuideSchema):
        self.schema = schema
        self.errors: List[CdmValidationError] = []

        # --- THIS IS THE FIX ---
        # 1. Detect delimiters ONCE from the raw string.
        delims = self._detect_delimiters(edi_string)
        self.element_delimiter, self.segment_terminator, self.component_separator = delims
        
        # 2. Segmentize the string using the DETECTED delimiters.
        self.all_segments: List[CdmSegment] = self._segmentize(edi_string)
        
        # 3. Initialize the validator.
        self.validator = SegmentValidator(schema, self.component_separator)
        logger.debug(f"Parser initialized with {len(self.all_segments)} segments.")
        # --- END OF FIX ---

    def _detect_delimiters(self, edi_string: str) -> Tuple[str, str, str]:
        clean_edi = edi_string.strip()
        if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
            # Positions are fixed in the X12 standard
            element_delimiter = clean_edi[3]
            segment_terminator = clean_edi[105]
            component_separator = clean_edi[104]
            logger.debug(f"Delimiters detected: Element='{element_delimiter}', Segment='{segment_terminator}', Component='{component_separator}'")
            return element_delimiter, segment_terminator, component_separator
        logger.warning("Could not find standard ISA segment. Falling back to default delimiters ('*', '~', ':').")
        return '*', '~', ':'

    # Renamed from _segmentize_and_parse for clarity and removed its internal delimiter detection
    def _segmentize(self, edi_string: str) -> List[CdmSegment]:
        segments = []
        edi_content = edi_string.strip().replace('\r\n', '\n').replace('\r', '\n')
        if self.segment_terminator != '\n':
            edi_content = edi_content.replace('\n', '')
        
        raw_segments = edi_content.split(self.segment_terminator)
        for i, seg_str in enumerate(raw_segments):
            clean_seg = seg_str.strip()
            if not clean_seg: continue
            
            parts = clean_seg.split(self.element_delimiter)
            segment_id = parts[0]
            
            elements: List[CdmElement] = [CdmElement(value=value, position=idx + 1) for idx, value in enumerate(parts[1:])]

            segments.append(CdmSegment(segment_id=segment_id, elements=elements, line_number=i + 1, raw_segment=clean_seg))
            if segment_id == 'IEA': break
        return segments
    
    def _find_next_segment(self, segment_id: str, segments: List[CdmSegment], start_index: int) -> int:
        for i in range(start_index, len(segments)):
            if segments[i].segment_id == segment_id:
                return i
        return -1
    
    def _get_starting_segment_id(self, node: StructureChild) -> Optional[str]:
        if isinstance(node, StructureSegment):
            return node.xid
        if isinstance(node, StructureLoop) and node.children:
            return self._get_starting_segment_id(node.children[0])
        return None

    # --- START OF FIX: NEW HELPER FUNCTION ---
    def _find_best_schema_match(
        self,
        current_segment: CdmSegment,
        schema_nodes: List[StructureChild],
        usage_counts: Dict[int, int],
    ) -> Tuple[Optional[StructureChild], int]:
        """
        Finds the best schema node for the current data segment by performing trial validations.

        Iterates through available schema nodes, checking for ID matches and usage limits.
        For each potential match, it performs a trial validation. The first schema node
        that validates without any "identifier" errors is considered the best match.
        """
        logger.debug(f"          -> Searching for best match for '{current_segment.segment_id}' among {len(schema_nodes)} schema nodes.")
        for i, schema_node in enumerate(schema_nodes):
            # 1. Check if the schema node has been used up to its max repeats
            max_repeats_str = getattr(schema_node, 'max_use', getattr(schema_node, 'repeat', '1'))
            try:
                max_repeats = int(max_repeats_str)
            except (ValueError, TypeError):
                max_repeats = 99999 # Corresponds to '>1' or similar
            
            current_usage = usage_counts.get(i, 0)
            if current_usage >= max_repeats:
                logger.debug(f"             - Skipping node {i} ('{schema_node.xid}'): Max usage ({max_repeats}) reached.")
                continue

            # 2. Check if the segment ID matches (for both segments and loops)
            starting_segment_id = self._get_starting_segment_id(schema_node)
            if current_segment.segment_id != starting_segment_id:
                logger.debug(f"             - Skipping node {i} ('{schema_node.xid}'): ID mismatch (expected '{starting_segment_id}').")
                continue

            logger.debug(f"             - Potential match found for '{current_segment.segment_id}' with schema node {i} ('{schema_node.xid}'). Performing trial validation.")
            
            # 3. Perform a trial validation to confirm this is the correct contextual definition
            context_id = None
            if isinstance(schema_node, StructureSegment):
                context_id = schema_node.contextDefinitionId
            elif isinstance(schema_node, StructureLoop) and schema_node.children:
                first_child = schema_node.children[0]
                if isinstance(first_child, StructureSegment):
                    context_id = first_child.contextDefinitionId

            trial_errors = self.validator.validate(current_segment, context_id)
            identifier_errors = [e for e in trial_errors if e.is_identifier_error]

            if not identifier_errors:
                logger.debug(f"               - Trial validation PASSED for node {i} ('{schema_node.xid}') with context '{context_id}'. This is the best match.")
                return schema_node, i
            else:
                logger.debug(f"               - Trial validation FAILED for node {i} ('{schema_node.xid}') with identifier errors: {[e.message for e in identifier_errors]}.")
                
        logger.debug(f"          -> No suitable match found for '{current_segment.segment_id}' in this loop.")
        return None, -1
    # --- END OF FIX ---

    # --- START OF FIX: REPLACED _build_tree FUNCTION ---
    def _build_tree(self, segments: List[CdmSegment], schema_nodes: List[StructureChild], depth=0, parent_loop_id: str = "root") -> Tuple[CdmLoop, int]:
        indent = "  " * depth
        cdm_loop = CdmLoop(loop_id=parent_loop_id)
        cursor = 0
        usage_counts = {i: 0 for i in range(len(schema_nodes))}

        logger.debug(f"{indent}[PARSE START - LOOP {parent_loop_id}] Processing {len(segments)} data segments against {len(schema_nodes)} schema nodes.")

        while cursor < len(segments):
            current_segment = segments[cursor]
            logger.debug(f"{indent}[SEGMENT {cursor+1}/{len(segments)}] Processing '{current_segment.segment_id}' (line {current_segment.line_number})")

            schema_node, schema_node_index = self._find_best_schema_match(
                current_segment, schema_nodes, usage_counts
            )

            if schema_node:
                logger.debug(f"{indent}  -> [MATCH FOUND] Data '{current_segment.segment_id}' matched schema node '{schema_node.xid}' (index {schema_node_index})")
                # A valid node was found, process it.
                if isinstance(schema_node, StructureSegment):
                    # Perform final validation and add segment
                    validation_errors = self.validator.validate(current_segment, schema_node.contextDefinitionId)
                    if validation_errors:
                        current_segment.errors.extend(validation_errors)
                    cdm_loop.segments.append(current_segment)
                    cursor += 1
                
                elif isinstance(schema_node, StructureLoop):
                    # Recursively parse the sub-loop
                    logger.debug(f"{indent}  -> Entering sub-loop '{schema_node.xid}'")
                    sub_loop, segments_consumed = self._build_tree(segments[cursor:], schema_node.children, depth + 1, parent_loop_id=schema_node.xid)
                    logger.debug(f"{indent}  -> Exited sub-loop '{schema_node.xid}', consumed {segments_consumed} segments.")
                    cdm_loop.add_loop(sub_loop)
                    cdm_loop.errors.extend(sub_loop.errors)
                    cursor += segments_consumed
                
                usage_counts[schema_node_index] += 1
            else:
                # No valid schema node could be found for the current data segment in this loop.
                logger.debug(f"{indent}  -> [NO MATCH] Segment '{current_segment.segment_id}' does not match any remaining valid children of '{parent_loop_id}'. Breaking loop.")
                break # Exit the loop and return to the parent.

        # After the loop, check if any mandatory segments/loops were missed.
        for i, node in enumerate(schema_nodes):
            if node.usage == 'R' and usage_counts.get(i, 0) == 0:
                error_msg = f"Required segment or loop '{node.xid}' ({node.name}) is missing from loop '{parent_loop_id}'."
                logger.warning(f"{indent}[STRUCTURAL ERROR] {error_msg}")
                cdm_loop.errors.append(CdmValidationError(message=error_msg))

        logger.debug(f"{indent}[PARSE END - LOOP {parent_loop_id}] Consumed {cursor}/{len(segments)} segments.")
        return cdm_loop, cursor
    # --- END OF FIX ---

    def _parse_transaction_set(self, segments: List[CdmSegment]) -> CdmTransaction:
        st_segment = segments[0]
        se_segment = segments[-1]
        transaction_body_segments = segments[1:-1]

        logger.info(f"=== PARSING TRANSACTION SET {st_segment.elements[1].value if len(st_segment.elements) > 1 else 'UNKNOWN'} ===")
        logger.info(f"Transaction contains {len(transaction_body_segments)} body segments (lines {transaction_body_segments[0].line_number if transaction_body_segments else 'N/A'}-{transaction_body_segments[-1].line_number if transaction_body_segments else 'N/A'})")

        try:
            logger.debug("Attempting to find ST_LOOP in schema structure...")
            st_loop_schema = next((n for n in self.schema.structure if isinstance(n, StructureLoop) and n.xid == 'ST_LOOP'), None)
            if not st_loop_schema:
                isa_loop = next((n for n in self.schema.structure if isinstance(n, StructureLoop) and n.xid == 'ISA_LOOP'), None)
                if not isa_loop or not isa_loop.children: raise ValueError("ISA_LOOP not found in schema structure")
                gs_loop = next((n for n in isa_loop.children if isinstance(n, StructureLoop) and n.xid == 'GS_LOOP'), None)
                if not gs_loop or not gs_loop.children: raise ValueError("GS_LOOP not found in schema structure")
                st_loop_schema = next((n for n in gs_loop.children if isinstance(n, StructureLoop) and n.xid == 'ST_LOOP'), None)
                if not st_loop_schema: raise ValueError("ST_LOOP not found in schema structure")

            st_loop_children = [child for child in st_loop_schema.children if child.xid not in ('ST', 'SE')]
            logger.info(f"Found ST_LOOP with {len(st_loop_children)} expected child structures: {[child.xid for child in st_loop_children]}")

            body_loop, consumed_count = self._build_tree(transaction_body_segments, st_loop_children, depth=1, parent_loop_id="ST_LOOP")

            transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
            transaction.errors.extend(body_loop.errors)

            if consumed_count < len(transaction_body_segments):
                unparsed_segments = transaction_body_segments[consumed_count:]
                problematic_segment = unparsed_segments[0]
                error_msg = f"Transaction parsing incomplete. Could not process {len(unparsed_segments)} remaining segments starting with '{problematic_segment.segment_id}' (line {problematic_segment.line_number}). This may indicate an unsupported structure or validation issue."
                logger.warning(error_msg)
                logger.warning(f"Unparsed segments: {', '.join([f'{seg.segment_id}(L{seg.line_number})' for seg in unparsed_segments[:5]])}{'...' if len(unparsed_segments) > 5 else ''}")
                transaction.errors.append(CdmValidationError(message=error_msg, line_number=problematic_segment.line_number, segment_id=problematic_segment.segment_id))
            else:
                logger.info(f"Transaction parsed successfully. Consumed all {consumed_count} segments.")

        except Exception as e:
            logger.error(f"Critical error parsing transaction set: {str(e)}", exc_info=True)
            # Create a minimal transaction with the error
            transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=CdmLoop(loop_id="ST_LOOP"))
            transaction.errors.append(CdmValidationError(message=f"Critical parsing error: {str(e)}", line_number=st_segment.line_number, segment_id=st_segment.segment_id))

        logger.info(f"=== TRANSACTION SET PARSING COMPLETE ({len(transaction.errors)} errors) ===")
        return transaction

    def _collect_all_errors(self, interchange: CdmInterchange) -> List[Tuple[str, CdmValidationError]]:
        all_errors: List[Tuple[str, CdmValidationError]] = []
        for error in interchange.errors:
            all_errors.append(("Interchange", error))

        for group in interchange.functional_groups:
            for error in group.errors:
                all_errors.append(("Functional Group", error))
            for transaction in group.transactions:
                for error in transaction.errors:
                    all_errors.append(("Transaction", error))

                def collect_loop_errors(loop: CdmLoop, path: str):
                    for error in loop.errors:
                        all_errors.append((f"Loop {path}", error))
                    for segment in loop.segments:
                        for error in segment.errors:
                            all_errors.append((f"Segment {segment.raw_segment} (Line: {segment.line_number})", error))
                    for loop_id, sub_loops in loop.loops.items():
                        for i, sub_loop in enumerate(sub_loops):
                            collect_loop_errors(sub_loop, f"{path}/{loop_id}[{i}]")

                collect_loop_errors(transaction.body, "ST_LOOP")
        return all_errors

    def parse(self) -> CdmInterchange:
        self.errors.clear()
        isa_idx = self._find_next_segment('ISA', self.all_segments, 0)
        iea_idx = self._find_next_segment('IEA', self.all_segments, isa_idx if isa_idx != -1 else 0)

        if isa_idx == -1 or iea_idx == -1:
            self.errors.append(CdmValidationError(message="ISA/IEA envelope not found."))
            dummy_isa = CdmSegment(segment_id='ISA', elements=[], line_number=0, raw_segment='')
            dummy_iea = CdmSegment(segment_id='IEA', elements=[], line_number=0, raw_segment='')
            return CdmInterchange(header=dummy_isa, trailer=dummy_iea, errors=self.errors)
        
        isa_segment = self.all_segments[isa_idx]
        iea_segment = self.all_segments[iea_idx]
        isa_segment.errors.extend(self.validator.validate(isa_segment))
        iea_segment.errors.extend(self.validator.validate(iea_segment))
        
        interchange = CdmInterchange(header=isa_segment, trailer=iea_segment)
        
        group_segments = self.all_segments[isa_idx + 1:iea_idx]
        cursor = 0
        while cursor < len(group_segments):
            gs_idx = self._find_next_segment('GS', group_segments, cursor)
            if gs_idx == -1: break
            ge_idx = self._find_next_segment('GE', group_segments, gs_idx)
            if ge_idx == -1:
                interchange.errors.append(CdmValidationError(message=f"Unclosed functional group at line {group_segments[gs_idx].line_number}."))
                break

            gs_segment = group_segments[gs_idx]
            ge_segment = group_segments[ge_idx]
            gs_segment.errors.extend(self.validator.validate(gs_segment))
            ge_segment.errors.extend(self.validator.validate(ge_segment))
            
            func_group = CdmFunctionalGroup(header=gs_segment, trailer=ge_segment)
            
            transaction_segments = group_segments[gs_idx + 1:ge_idx]
            ts_cursor = 0
            while ts_cursor < len(transaction_segments):
                st_idx = self._find_next_segment('ST', transaction_segments, ts_cursor)
                if st_idx == -1: break
                se_idx = self._find_next_segment('SE', transaction_segments, st_idx)
                if se_idx == -1:
                    interchange.errors.append(CdmValidationError(message=f"Unclosed transaction set at line {transaction_segments[st_idx].line_number}."))
                    break
                single_transaction_block = transaction_segments[st_idx : se_idx + 1]
                cdm_transaction = self._parse_transaction_set(single_transaction_block)
                func_group.transactions.append(cdm_transaction)
                ts_cursor = se_idx + 1
            interchange.functional_groups.append(func_group)
            cursor = ge_idx + 1

        all_errors = self._collect_all_errors(interchange)
        if all_errors:
            logger.warning("--- EDI PARSE & VALIDATION SUMMARY: ERRORS FOUND ---")
            logger.warning(f"Total Errors: {len(all_errors)}")
            for location, error in all_errors:
                logger.warning(f"  - Location: {location}")
                logger.warning(f"    - Error: {error.message}")
            logger.warning("--- END OF SUMMARY ---")
        else:
            logger.info("--- EDI PARSE & VALIDATION SUMMARY: SUCCESS ---")
            logger.info("No errors found in the document.")
            logger.info("--- END OF SUMMARY ---")

        return interchange