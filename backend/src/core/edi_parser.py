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

    # --- THIS IS THE RESTORED/ENHANCED METHOD WITH DETAILED LOGGING ---
    def _validate_element_recursively(self, element_def: Dict[str, Any], value: str, parent_xid: Optional[str] = None) -> List[CdmValidationError]:
        errors: List[CdmValidationError] = []
        xid = element_def.get("xid")
        full_xid = f"{parent_xid}-{xid}" if parent_xid else xid
        usage = element_def.get("usage", "S")
        is_present = value != ""
        
        log_line_intro = f"      Validating {full_xid} (Usage: {usage}): Data='{value}'"

        if usage == 'R' and not is_present:
            err_msg = f"Required element '{full_xid}' is missing."
            logger.debug(f"{log_line_intro} -> [FAIL] {err_msg}")
            errors.append(CdmValidationError(message=err_msg))
            return errors
        
        if usage == 'N' and is_present:
            err_msg = f"Element '{full_xid}' is Not Used and should not contain data."
            logger.debug(f"{log_line_intro} -> [FAIL] {err_msg}")
            errors.append(CdmValidationError(message=err_msg))
        
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
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value is shorter than min length {min_len}."))
            validation_passed = False
        if max_len is not None and len(value) > max_len:
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value is longer than max length {max_len}."))
            validation_passed = False

        if data_type and not _validate_data_type(value, data_type):
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value does not match expected data type '{data_type}'."))
            validation_passed = False
        data_format = element_def.get('format')
        if data_format and not _validate_format(value, data_format):
            errors.append(CdmValidationError(message=f"Element '{full_xid}': Value does not match expected format '{data_format}'."))
            validation_passed = False

        if "valid_codes" in element_def and element_def["valid_codes"]:
            allowed_codes = {str(c['code']) for c in element_def["valid_codes"]}
            if value not in allowed_codes:
                errors.append(CdmValidationError(message=f"Element '{full_xid}': Invalid code value. Allowed: {', '.join(sorted(list(allowed_codes)))}."))
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

# FILE: backend/src/core/edi_parser.py
# REPLACE the existing _build_tree method with this one.

    def _build_tree(self, segments: List[CdmSegment], schema_nodes: List[StructureChild], depth=0, parent_loop_id: str = "root") -> Tuple[CdmLoop, int]:
        indent = "  " * depth
        cdm_loop = CdmLoop(loop_id=parent_loop_id)
        cursor = 0
        schema_node_index = 0
        
        usage_counts = {i: 0 for i in range(len(schema_nodes))}

        logger.debug(f"{indent}[PARSE START - LOOP {parent_loop_id}] Processing {len(segments)} data segments against {len(schema_nodes)} schema nodes.")

        while cursor < len(segments):
            current_segment = segments[cursor]
            
            # If we've exhausted our schema, this segment belongs to a parent loop.
            if schema_node_index >= len(schema_nodes):
                logger.debug(f"{indent}  -> No more schema nodes in '{parent_loop_id}'. Segment '{current_segment.segment_id}' is for a parent. Breaking.")
                break

            schema_node = schema_nodes[schema_node_index]
            max_repeats = getattr(schema_node, 'max_use', getattr(schema_node, 'repeat', 1))
            if not isinstance(max_repeats, int): max_repeats = 99999
            
            # If the current schema node is maxed out, advance the schema pointer and retry the same data segment.
            if usage_counts.get(schema_node_index, 0) >= max_repeats:
                schema_node_index += 1
                continue

            is_id_match = (isinstance(schema_node, StructureSegment) and current_segment.segment_id == schema_node.xid) or \
                        (isinstance(schema_node, StructureLoop) and self._get_starting_segment_id(schema_node) == current_segment.segment_id)
            
            if is_id_match:
                # For segments, we must confirm the context is correct via trial validation.
                if isinstance(schema_node, StructureSegment):
                    validation_errors = self.validator.validate(current_segment, schema_node.contextDefinitionId)
                    if validation_errors:
                        ambiguous_match_possible = any(
                            (isinstance(node, StructureSegment) and node.xid == current_segment.segment_id)
                            for node in schema_nodes[schema_node_index + 1:]
                        )
                        if ambiguous_match_possible:
                            # Ambiguous (like REF). Skip this schema context and try the next one.
                            schema_node_index += 1
                            continue # Retry same data segment
                        else:
                            # Unambiguous (like PAT). Commit the match with its errors.
                            current_segment.errors.extend(validation_errors)

                # --- Confirmed Match Processing ---
                logger.debug(f"{indent}  -> [MATCH CONFIRMED] for '{current_segment.segment_id}' with schema node '{schema_node.xid}'.")
                if isinstance(schema_node, StructureSegment):
                    cdm_loop.segments.append(current_segment)
                    cursor += 1
                elif isinstance(schema_node, StructureLoop):
                    sub_loop, segments_consumed = self._build_tree(segments[cursor:], schema_node.children, depth + 1, parent_loop_id=schema_node.xid)
                    cdm_loop.add_loop(sub_loop)
                    cdm_loop.errors.extend(sub_loop.errors)
                    cursor += segments_consumed

                usage_counts[schema_node_index] = usage_counts.get(schema_node_index, 0) + 1
            
            else: # The data segment does NOT match the current schema node.
                is_truly_required = schema_node.usage == 'R' and usage_counts.get(schema_node_index, 0) == 0
                if is_truly_required:
                    error_msg = f"Required segment or loop '{schema_node.xid}' ({schema_node.name}) not found. Found '{current_segment.segment_id}' instead."
                    logger.warning(f"{indent}[FAIL] {error_msg}")
                    cdm_loop.errors.append(CdmValidationError(message=error_msg, line_number=current_segment.line_number, segment_id=current_segment.segment_id))
                    # This is the key change: we break from the loop and return the current cursor,
                    # indicating that this loop is structurally broken and parsing cannot continue within it.
                    break
                else:
                    # The schema node was optional or a used repeating required node.
                    # Skip the schema node and retry the same data segment against the next one.
                    logger.debug(f"{indent}  -> Data '{current_segment.segment_id}' does not match optional/repeating schema node '{schema_node.xid}'. Skipping schema node.")
                    schema_node_index += 1

        # After the loop, check for any unsatisfied required nodes at the end.
        for i in range(schema_node_index, len(schema_nodes)):
            remaining_node = schema_nodes[i]
            if remaining_node.usage == 'R' and usage_counts.get(i, 0) == 0:
                error_msg = f"Required segment or loop '{remaining_node.xid}' ({remaining_node.name}) is missing at the end of its parent loop '{parent_loop_id}'."
                logger.warning(f"{indent}[FAIL] {error_msg}")
                cdm_loop.errors.append(CdmValidationError(message=error_msg))

        logger.debug(f"{indent}[PARSE END - LOOP {parent_loop_id}] Consumed {cursor} segments.")
        return cdm_loop, cursor

    def _parse_transaction_set(self, segments: List[CdmSegment]) -> CdmTransaction:
        st_segment = segments[0]
        se_segment = segments[-1]
        transaction_body_segments = segments[1:-1]
        
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
        logger.debug("Found ST_LOOP. Parsing transaction body...")

        body_loop, consumed_count = self._build_tree(transaction_body_segments, st_loop_children, depth=1, parent_loop_id="ST_LOOP")

        transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
        transaction.errors.extend(body_loop.errors)

        if consumed_count < len(transaction_body_segments):
            problematic_segment = transaction_body_segments[consumed_count]
            error_msg = f"Transaction parsing incomplete. Unexpected structure starting at segment '{problematic_segment.segment_id}' (line {problematic_segment.line_number})."
            logger.warning(error_msg)
            transaction.errors.append(CdmValidationError(message=error_msg, line_number=problematic_segment.line_number, segment_id=problematic_segment.segment_id))
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