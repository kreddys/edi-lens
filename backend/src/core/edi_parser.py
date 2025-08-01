import logging
import copy
import re
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from src.edi_schemas.edi_guide import ImplementationGuideSchema, StructureLoop, StructureSegment, StructureChild
from src.core.cdm import CdmInterchange, CdmFunctionalGroup, CdmTransaction, CdmLoop, CdmSegment, CdmElement, CdmValidationError

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
        # This is the only part of the validator that needs changing.
        # We add the context_id to the initial log message for clarity.
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

        for rule in rules:
            conditions_met = self._evaluate_conditions(segment, rule.get("conditions", {}))
            if conditions_met:
                for assertion in rule.get("then", []):
                    errors.extend(self._execute_assertion(segment, assertion, rule.get('ruleId')))
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
        
        if op == "IS_PRESENT": return value.strip() != ""
        if op == "IS_NOT_PRESENT": return value.strip() == ""
        if op == "IS": return value == clause["value"]
        if op == "IS_NOT": return value != clause["value"]
        return False

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
        return errors

    def _validate_element_recursively(self, element_def: Dict[str, Any], value: str, parent_xid: Optional[str] = None) -> List[CdmValidationError]:
        errors: List[CdmValidationError] = []
        xid = element_def.get("xid")
        full_xid = f"{parent_xid}-{xid}" if parent_xid else xid
        usage = element_def.get("usage", "S")
        is_present = value != ""
        is_identifier = element_def.get("is_identifier", False)

        log_line_intro = f"      Validating {full_xid} (Usage: {usage}): Data='{value}'"

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

        validation_passed = True
        
        min_len, max_len = element_def.get('minLength'), element_def.get('maxLength')
        if min_len is not None and len(value) < min_len:
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value is shorter than min length {min_len}.", element_xid=full_xid, is_identifier_error=is_identifier))
            validation_passed = False
        if max_len is not None and len(value) > max_len:
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value is longer than max length {max_len}.", element_xid=full_xid, is_identifier_error=is_identifier))
            validation_passed = False

        if data_type and not _validate_data_type(value, data_type):
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value does not match expected data type '{data_type}'.", element_xid=full_xid, is_identifier_error=is_identifier))
            validation_passed = False
        data_format = element_def.get('format')
        if data_format and not _validate_format(value, data_format):
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value does not match expected format '{data_format}'.", element_xid=full_xid, is_identifier_error=is_identifier))
            validation_passed = False

        if "valid_codes" in element_def and element_def["valid_codes"]:
            allowed_codes = {str(c['code']) for c in element_def["valid_codes"]}
            if value not in allowed_codes:
                errors.append(CdmValidationError(message=f"Element '{full_xid}': Invalid code value. Allowed: {', '.join(sorted(list(allowed_codes)))}.", element_xid=full_xid, is_identifier_error=is_identifier))
                validation_passed = False

        if validation_passed:
            logger.debug(f"{log_line_intro} -> [PASS]")
        else:
            logger.debug(f"{log_line_intro} -> [FAIL] One or more validation checks failed.")

        return errors

class EdiParser:
    def __init__(self, edi_string: str, schema: ImplementationGuideSchema):
        self.schema = schema
        _, _, component_separator = self._detect_delimiters(edi_string)
        self.validator = SegmentValidator(schema, component_separator)
        self.all_segments: List[CdmSegment] = self._segmentize_and_parse(edi_string)
        self.errors: List[CdmValidationError] = []
        logger.debug(f"Parser initialized with {len(self.all_segments)} segments.")

    def _detect_delimiters(self, edi_string: str) -> Tuple[str, str, str]:
        clean_edi = edi_string.strip()
        if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
            element_delimiter = clean_edi[103]
            segment_terminator = clean_edi[105]
            component_separator = clean_edi[104]
            return element_delimiter, segment_terminator, component_separator
        logger.warning("Could not find standard ISA segment. Falling back to default delimiters ('*', '~', ':').")
        return '*', '~', ':'

    def _segmentize_and_parse(self, edi_string: str) -> List[CdmSegment]:
        element_delimiter, segment_terminator, _ = self._detect_delimiters(edi_string)
        segments = []
        edi_content = edi_string.strip().replace('\r\n', '\n').replace('\r', '\n')
        if segment_terminator != '\n':
            edi_content = edi_content.replace('\n', '')
        raw_segments = edi_content.split(segment_terminator)
        for i, seg_str in enumerate(raw_segments):
            clean_seg = seg_str.strip()
            if not clean_seg: continue
            
            parts = clean_seg.split(element_delimiter)
            segment_id = parts[0]
            
            elements: List[CdmElement] = []
            for idx, value in enumerate(parts[1:]):
                elements.append(CdmElement(value=value, position=idx + 1))

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
    
    def _find_best_schema_match(
        self,
        current_segment: CdmSegment,
        schema_nodes: List[StructureChild],
        usage_counts: Dict[int, int],
        start_index: int,
    ) -> Optional[Tuple[StructureChild, int]]:
        """
        Finds the best schema node for the current data segment by performing trial validations.

        Iterates through available schema nodes starting from `start_index`.
        For each node, it checks if the segment ID matches and if a trial validation passes.
        It returns the first schema node that is a valid match.
        """
        for i in range(start_index, len(schema_nodes)):
            schema_node = schema_nodes[i]

            # 1. Check if the schema node has been used up to its max repeats
            max_repeats = getattr(schema_node, 'max_use', getattr(schema_node, 'repeat', 1))
            if not isinstance(max_repeats, int): max_repeats = 99999
            if usage_counts.get(i, 0) >= max_repeats:
                continue

            # 2. Check if the segment ID matches (for both segments and loops)
            is_potential_match = False
            if isinstance(schema_node, StructureSegment) and current_segment.segment_id == schema_node.xid:
                is_potential_match = True
            elif isinstance(schema_node, StructureLoop) and self._get_starting_segment_id(schema_node) == current_segment.segment_id:
                is_potential_match = True
            
            if is_potential_match and isinstance(schema_node, StructureSegment):
                # 3. Perform a trial validation to see if this is the correct contextual definition
                trial_errors = self.validator.validate(current_segment, schema_node.contextDefinitionId)
                if not trial_errors:
                    # This is a valid match. Return the node and its index.
                    return schema_node, i
            elif is_potential_match and isinstance(schema_node, StructureLoop):
                # For loops, we assume the ID match is sufficient.
                return schema_node, i
                
        return None, -1 # No suitable match found    

    def _build_tree(self, segments: List[CdmSegment], schema_nodes: List[StructureChild], depth=0, parent_loop_id: str = "root") -> Tuple[CdmLoop, int]:
        indent = "  " * depth
        cdm_loop = CdmLoop(loop_id=parent_loop_id)
        cursor = 0
        schema_node_index = 0
        usage_counts = {i: 0 for i in range(len(schema_nodes))}

        logger.debug(f"{indent}[PARSE START - LOOP {parent_loop_id}] Processing {len(segments)} data segments against {len(schema_nodes)} schema nodes.")
        logger.debug(f"{indent}Schema nodes: {[f'{node.xid}({node.usage})' for node in schema_nodes]}")

        # Safety mechanism to prevent infinite loops
        max_iterations = len(segments) * len(schema_nodes) * 2  # Allow some retry attempts
        iteration_count = 0
        
        while cursor < len(segments) and iteration_count < max_iterations:
            iteration_count += 1
            current_segment = segments[cursor]
            logger.debug(f"{indent}[SEGMENT {cursor+1}/{len(segments)}] Processing '{current_segment.segment_id}' (line {current_segment.line_number}) [iteration {iteration_count}]")
            
            # Safety check for infinite loops
            if iteration_count >= max_iterations:
                logger.error(f"{indent}[INFINITE LOOP DETECTED] Breaking out of parsing loop after {iteration_count} iterations")
                break
            
            if schema_node_index >= len(schema_nodes):
                logger.debug(f"{indent}  -> No more schema nodes in '{parent_loop_id}'. Segment '{current_segment.segment_id}' cannot be processed here. Breaking to return to parent.")
                break

            schema_node = schema_nodes[schema_node_index]
            max_repeats = getattr(schema_node, 'max_use', getattr(schema_node, 'repeat', 1))
            if not isinstance(max_repeats, int): max_repeats = 99999
            current_usage = usage_counts.get(schema_node_index, 0)
            
            logger.debug(f"{indent}  -> Trying schema node [{schema_node_index}]: '{schema_node.xid}' ({schema_node.usage}, used {current_usage}/{max_repeats})")
            
            if current_usage >= max_repeats:
                logger.debug(f"{indent}     -> Schema node '{schema_node.xid}' already used maximum times ({max_repeats}). Moving to next.")
                schema_node_index += 1
                continue

            is_id_match = (isinstance(schema_node, StructureSegment) and current_segment.segment_id == schema_node.xid) or \
                        (isinstance(schema_node, StructureLoop) and self._get_starting_segment_id(schema_node) == current_segment.segment_id)
            
            # Pre-flight validation for loops to prevent infinite recursion on identifier mismatch
            if is_id_match and isinstance(schema_node, StructureLoop):
                logger.debug(f"{indent}     -> ID match for LOOP '{schema_node.xid}'. Performing pre-flight validation...")
                # The first child of a loop must be a segment that defines its identity
                first_child_segment_def = schema_node.children[0] if schema_node.children else None
                if isinstance(first_child_segment_def, StructureSegment):
                    context_id = first_child_segment_def.contextDefinitionId
                    logger.debug(f"{indent}     -> Validating against first child context: '{context_id}'")
                    trial_errors = self.validator.validate(current_segment, context_id)
                    identifier_errors = [e for e in trial_errors if e.is_identifier_error]
                    
                    if identifier_errors:
                        logger.debug(f"{indent}     -> [PRE-FLIGHT FAIL] Identifier validation failed: {[e.message for e in identifier_errors]}")
                        logger.debug(f"{indent}     -> This is not the correct loop. Trying next schema node.")
                        schema_node_index += 1
                        continue
                    else:
                        logger.debug(f"{indent}     -> [PRE-FLIGHT PASS] Loop validation successful for '{schema_node.xid}'")
                else:
                    logger.debug(f"{indent}     -> Loop '{schema_node.xid}' has no segment children for validation. Accepting ID match.")

            if is_id_match:
                logger.debug(f"{indent}     -> Processing confirmed ID match...")
                # This block is now only for segments or confirmed-valid loops
                validation_errors = []
                if isinstance(schema_node, StructureSegment):
                    logger.debug(f"{indent}     -> Validating SEGMENT against context: '{schema_node.contextDefinitionId}'")
                    validation_errors = self.validator.validate(current_segment, schema_node.contextDefinitionId)
                
                # A segment-level identifier error is simpler to handle as it doesn't cause a loop
                has_identifier_error = any(e.is_identifier_error for e in validation_errors)
                
                if not has_identifier_error:
                    logger.debug(f"{indent}     -> [MATCH CONFIRMED] '{current_segment.segment_id}' successfully matched schema node '{schema_node.xid}'")
                    if validation_errors:
                        logger.debug(f"{indent}     -> Non-critical validation issues: {len(validation_errors)} errors")
                    
                    if validation_errors:
                        current_segment.errors.extend(validation_errors)
                        logger.warning(f"{indent}    -> Segment '{current_segment.segment_id}' matched an unambiguous schema node but failed validation. Accepting with non-critical errors.")

                    if isinstance(schema_node, StructureSegment):
                        logger.debug(f"{indent}     -> Adding SEGMENT '{current_segment.segment_id}' to loop '{parent_loop_id}'")
                        cdm_loop.segments.append(current_segment)
                        cursor += 1
                    elif isinstance(schema_node, StructureLoop):
                        logger.debug(f"{indent}     -> Starting sub-loop '{schema_node.xid}' with {len(segments[cursor:])} remaining segments")
                        sub_loop, segments_consumed = self._build_tree(segments[cursor:], schema_node.children, depth + 1, parent_loop_id=schema_node.xid)
                        logger.debug(f"{indent}     -> Sub-loop '{schema_node.xid}' consumed {segments_consumed} segments and returned {len(sub_loop.errors)} errors")
                        cdm_loop.add_loop(sub_loop)
                        cdm_loop.errors.extend(sub_loop.errors)
                        cursor += segments_consumed

                    usage_counts[schema_node_index] = usage_counts.get(schema_node_index, 0) + 1
                    new_usage = usage_counts[schema_node_index]
                    logger.debug(f"{indent}     -> Schema node '{schema_node.xid}' now used {new_usage}/{max_repeats} times")
                    if new_usage >= max_repeats:
                        logger.debug(f"{indent}     -> Schema node '{schema_node.xid}' reached max usage. Moving to next schema node.")
                        schema_node_index += 1
                else:
                    logger.debug(f"{indent}     -> [SEGMENT VALIDATION FAIL] '{current_segment.segment_id}' matched '{schema_node.xid}' by ID but failed identifier validation")
                    logger.debug(f"{indent}     -> Identifier errors: {[e.message for e in validation_errors if e.is_identifier_error]}")
                    schema_node_index += 1
                    continue
            
            else:
                logger.debug(f"{indent}     -> No ID match with '{schema_node.xid}'")
                is_truly_required = schema_node.usage == 'R' and usage_counts.get(schema_node_index, 0) == 0
                if is_truly_required:
                    error_msg = f"Required segment or loop '{schema_node.xid}' ({schema_node.name}) not found. Found '{current_segment.segment_id}' instead."
                    logger.warning(f"{indent}     -> [STRUCTURAL ERROR] {error_msg}")
                    cdm_loop.errors.append(CdmValidationError(message=error_msg, line_number=current_segment.line_number, segment_id=current_segment.segment_id))
                    # Don't break immediately - try to continue parsing for robustness
                    logger.debug(f"{indent}     -> Attempting to continue parsing despite structural error...")
                    schema_node_index += 1
                else:
                    logger.debug(f"{indent}     -> Schema node '{schema_node.xid}' is optional/already used. Moving to next schema node.")
                    schema_node_index += 1
                    
                    # CRITICAL FIX: If we've tried all schema nodes and none matched this segment,
                    # we must advance the cursor to prevent infinite loops
                    if schema_node_index >= len(schema_nodes):
                        logger.debug(f"{indent}     -> All schema nodes tried for segment '{current_segment.segment_id}'. This segment doesn't belong in loop '{parent_loop_id}'.")
                        break  # Let the outer logic handle this
            
            # Safety check: If we've exhausted all schema nodes, this segment doesn't belong here
            if schema_node_index >= len(schema_nodes):
                current_segment = segments[cursor] if cursor < len(segments) else None
                if current_segment:
                    logger.warning(f"{indent}[ORPHANED SEGMENT] Cannot place '{current_segment.segment_id}' (line {current_segment.line_number}) in loop '{parent_loop_id}' - exhausted all schema nodes")
                    logger.debug(f"{indent}This segment likely belongs to a parent loop. Ending current loop processing.")
                break

        # Check for missing required elements at the end of the loop
        missing_required = []
        for i in range(schema_node_index, len(schema_nodes)):
            remaining_node = schema_nodes[i]
            if remaining_node.usage == 'R' and usage_counts.get(i, 0) == 0:
                missing_required.append(remaining_node.xid)
                error_msg = f"Required segment or loop '{remaining_node.xid}' ({remaining_node.name}) is missing at the end of its parent loop '{parent_loop_id}'."
                logger.warning(f"{indent}[MISSING REQUIRED] {error_msg}")
                cdm_loop.errors.append(CdmValidationError(message=error_msg))
        
        if missing_required:
            logger.debug(f"{indent}Loop '{parent_loop_id}' completed with {len(missing_required)} missing required elements: {missing_required}")
        else:
            logger.debug(f"{indent}Loop '{parent_loop_id}' completed successfully - all required elements found")

        logger.debug(f"{indent}[PARSE END - LOOP {parent_loop_id}] Consumed {cursor}/{len(segments)} segments, created {len(cdm_loop.segments)} segments and {sum(len(loops) for loops in cdm_loop.loops.values())} child loops, {len(cdm_loop.errors)} errors")
        return cdm_loop, cursor

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
            logger.error(f"Critical error parsing transaction set: {str(e)}")
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