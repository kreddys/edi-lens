# FILE: backend/src/core/edi_parser.py
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
        return True # Composites are validated structurally
    if data_type in ['AN', 'ID']:
        return True # Assume valid for now, code/format checks will handle specifics
    if data_type in ('N0', 'N1', 'N2', 'R'):
        if not value: return True # Allow empty for optional numeric/decimal
        # Check if it can be converted to a number
        try:
            float(value)
            return True
        except ValueError:
            return False
    # For DT and TM, format validation is the real test
    if data_type in ('DT', 'TM'):
        return True
    return False

def _validate_format(value: str, data_format: str) -> bool:
    if not value: return True # Don't format-check empty optional fields
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
    return True # Default to true if format is unknown

def get_guide_version_from_edi(edi_string: str) -> Optional[str]:
    # ... (this function is correct and unchanged) ...
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

# In backend/src/core/edi_parser.py

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
            
            # --- THIS IS THE DEEP MERGE FIX ---
            if 'sub_elements' in overrides and 'sub_elements' in base_el:
                # If both have sub-elements, merge them deeply.
                base_sub_elements = base_el['sub_elements']
                override_sub_elements = overrides['sub_elements']
                
                # Handle both list and dict structures for sub-elements
                if isinstance(base_sub_elements, list) and isinstance(override_sub_elements, dict):
                    for j, base_sub_el in enumerate(base_sub_elements):
                        sub_el_xid = base_sub_el.get("xid")
                        if sub_el_xid in override_sub_elements:
                            # Apply the override to the base sub-element
                            base_sub_elements[j].update(override_sub_elements[sub_el_xid])
                
                # Remove sub_elements from the main override dict so it's not shallow-copied later
                del overrides['sub_elements']

            # Apply all other (non-sub-element) overrides
            for key, value in overrides.items():
                if value is not None:
                    effective["elements"][i][key] = value

    return effective

class SegmentValidator:
    def __init__(self, schema: ImplementationGuideSchema, component_separator: str):
        self.schema = schema
        self.component_separator = component_separator

    def validate(self, segment: CdmSegment, context_id: Optional[str] = None, depth=0) -> List[CdmValidationError]:
        indent = "  " * depth
        logger.debug(f"{indent}--- Validating Segment: '{segment.raw_segment}' (Context: {context_id or 'None'}) ---")
        errors: List[CdmValidationError] = []
        base_def_model = self.schema.segmentDefinitions.get(segment.segment_id)
        if not base_def_model:
            # ... (rest of the initial setup is unchanged)
            logger.warning(f"{indent}Validation FAILED: Base definition for '{segment.segment_id}' not found in schema.")
            return [CdmValidationError(message=f"Base definition for segment '{segment.segment_id}' not found in schema.")]
        
        base_def = base_def_model.model_dump(exclude_none=True)
        context_def_model = self.schema.contextualDefinitions.get(context_id) if context_id else None
        context_def = context_def_model.model_dump(exclude_none=True) if context_def_model else None
        
        effective_def = _get_effective_definition(base_def, context_def)
        elements_in_data = {el.position: el.value for el in segment.elements}
        element_indent = indent + "  "

        logger.debug(f"{element_indent}Processing {len(effective_def.get('elements', []))} defined elements...")
        for element_def in effective_def.get("elements", []):
            el_pos = element_def.get('seq')
            if not el_pos: continue
            value_in_data = elements_in_data.get(el_pos, "")
            errors.extend(self._validate_element_recursively(element_def, value_in_data, element_indent))
        
        # Syntax rules should be checked regardless of individual element validity.
        errors.extend(self._validate_syntax_rules(segment, effective_def, element_indent))

        logger.debug(f"{indent}--- Validation for '{segment.segment_id}' complete. Found {len(errors)} errors. ---")
        return errors

    def _validate_syntax_rules(self, segment: CdmSegment, effective_def: Dict[str, Any], indent: str) -> List[CdmValidationError]:
        """Validates inter-element syntax rules for a segment."""
        errors: List[CdmValidationError] = []
        rules = effective_def.get("rules", [])
        if not rules:
            return errors

        logger.debug(f"{indent}Processing {len(rules)} syntax rule(s)...")
        for rule in rules:
            conditions_met = self._evaluate_conditions(segment, rule.get("conditions", {}))
            if conditions_met:
                logger.debug(f"{indent}  Rule '{rule.get('ruleId')}': Conditions met, executing assertions.")
                for assertion in rule.get("then", []):
                    errors.extend(self._execute_assertion(segment, assertion, rule.get('ruleId')))
            else:
                logger.debug(f"{indent}  Rule '{rule.get('ruleId')}': Conditions not met, skipping.")
        return errors

    def _evaluate_conditions(self, segment: CdmSegment, conditions: Dict[str, Any]) -> bool:
        """Evaluates the ALL_OF or ANY_OF condition blocks."""
        if "ALL_OF" in conditions:
            return all(self._evaluate_condition_clause(segment, clause) for clause in conditions["ALL_OF"])
        if "ANY_OF" in conditions:
            return any(self._evaluate_condition_clause(segment, clause) for clause in conditions["ANY_OF"])
        return True # No conditions means the rule always applies

    def _evaluate_condition_clause(self, segment: CdmSegment, clause: Dict[str, Any]) -> bool:
        """Evaluates a single condition clause with detailed logging."""
        element_id = clause["element"]
        pos = int(re.sub(r'\D', '', element_id))
        value = segment.get_element(pos) or ""
        op = clause["operator"]
        
        result = False
        log_detail = ""

        if op == "IS_PRESENT":
            result = value.strip() != ""
            log_detail = f"Checking if '{element_id}' is present. Data='{value}'. Result: {result}"
        elif op == "IS_NOT_PRESENT":
            result = value.strip() == ""
            log_detail = f"Checking if '{element_id}' is not present. Data='{value}'. Result: {result}"
        elif op == "IS":
            expected_value = clause["value"]
            result = value == expected_value
            log_detail = f"Checking if '{element_id}' IS '{expected_value}'. Data='{value}'. Result: {result}"
        elif op == "IS_NOT":
            expected_value = clause["value"]
            result = value != expected_value
            log_detail = f"Checking if '{element_id}' IS NOT '{expected_value}'. Data='{value}'. Result: {result}"
        
        logger.debug(f"        Clause evaluation: {log_detail}")
        return result

    def _execute_assertion(self, segment: CdmSegment, assertion: Dict[str, Any], rule_id: str) -> List[CdmValidationError]:
        """Executes a single assertion with detailed logging and returns errors if it fails."""
        errors: List[CdmValidationError] = []
        assertion_type = assertion["assertion"]
        
        log_detail = ""
        assertion_failed = False

        if assertion_type == "MUST_BE_PRESENT":
            element_id = assertion["element"]
            pos = int(re.sub(r'\D', '', element_id))
            value = segment.get_element(pos) or ""
            if not (value and value.strip()):
                assertion_failed = True
            log_detail = f"Asserting {element_id} MUST BE PRESENT. Data='{value}'. Result: {'FAIL' if assertion_failed else 'PASS'}"

        elif assertion_type == "MUST_HAVE_LENGTH":
            element_id = assertion["element"]
            pos = int(re.sub(r'\D', '', element_id))
            value = segment.get_element(pos) or ""
            expected_length = assertion["value"]
            if len(value) != expected_length:
                assertion_failed = True
            log_detail = f"Asserting {element_id} MUST HAVE LENGTH {expected_length}. Data='{value}' (length={len(value)}). Result: {'FAIL' if assertion_failed else 'PASS'}"
        
        elif assertion_type == "ANY_OF_MUST_BE_PRESENT":
            element_ids = assertion["elements"]
            positions = [int(re.sub(r'\D', '', el_id)) for el_id in element_ids]
            if not any(segment.get_element(pos) for pos in positions):
                assertion_failed = True
            log_detail = f"Asserting ANY OF {', '.join(element_ids)} MUST BE PRESENT. Result: {'FAIL' if assertion_failed else 'PASS'}"

        logger.debug(f"          Assertion execution: {log_detail}")
        if assertion_failed:
            errors.append(CdmValidationError(message=f"Syntax Rule Failed ({rule_id}): {log_detail}"))
            
        return errors

    def _validate_element_recursively(self, element_def: Dict[str, Any], value: str, indent: str, parent_xid: Optional[str] = None) -> List[CdmValidationError]:
        """
        A unified, recursive function to validate an element or sub-element.
        """
        errors: List[CdmValidationError] = []
        xid = element_def.get("xid")
        full_xid = f"{parent_xid}-{xid}" if parent_xid else xid
        usage = element_def.get("usage", "S")
        
        # --- THIS IS THE FIX ---
        # Change the presence check from strip() != "" to just != ""
        # This correctly treats a field of spaces as "present" for length validation.
        is_present = value != ""
        
        log_line_intro = f"{indent}Validating {full_xid} (Usage: {usage}): Data='{value}'"

        if usage == 'R' and not is_present:
            err_msg = f"Required element '{full_xid}' is missing."
            logger.debug(f"{log_line_intro} -> [FAIL] {err_msg}")
            errors.append(CdmValidationError(message=err_msg))
            return errors
        
        if not is_present:
            if usage != 'N':
                 logger.debug(f"{log_line_intro} -> [PASS] Optional element is not present.")
            return errors

        data_type = element_def.get('dataType')
        if data_type == 'Composite':
            logger.debug(f"{log_line_intro} -> [INFO] Is Composite. Splitting with delimiter '{self.component_separator}'. Validating sub-elements.")
            sub_element_values = value.split(self.component_separator)
            sub_element_defs = element_def.get('sub_elements', [])
            
            if isinstance(sub_element_defs, list):
                for sub_def in sub_element_defs:
                    sub_pos = sub_def.get('seq')
                    if not sub_pos: continue
                    sub_value = sub_element_values[sub_pos - 1] if sub_pos - 1 < len(sub_element_values) else ""
                    errors.extend(self._validate_element_recursively(sub_def, sub_value, indent + "  ", parent_xid=full_xid))
            elif isinstance(sub_element_defs, dict):
                for sub_xid, sub_def in sub_element_defs.items():
                    try:
                        sub_pos = int(sub_xid.split('-')[-1])
                    except (ValueError, IndexError):
                        continue
                    sub_value = sub_element_values[sub_pos - 1] if sub_pos - 1 < len(sub_element_values) else ""
                    sub_def_with_xid = {'xid': sub_xid, **sub_def}
                    errors.extend(self._validate_element_recursively(sub_def_with_xid, sub_value, indent + "  ", parent_xid=full_xid))
            
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

    def _build_tree(self, segments: List[CdmSegment], schema_nodes: List[StructureChild], depth=0, parent_loop_id: str = "root") -> Tuple[CdmLoop, int]:
        indent = "  " * depth
        cdm_loop = CdmLoop(loop_id=parent_loop_id)
        cursor = 0
        schema_node_index = 0
        
        logger.debug(f"{indent}[START LOOP PARSE: {parent_loop_id}] Processing {len(segments)} segments against {len(schema_nodes)} schema nodes.")

        while cursor < len(segments) and schema_node_index < len(schema_nodes):
            schema_node = schema_nodes[schema_node_index]
            current_segment = segments[cursor]
            
            repeat_val = getattr(schema_node, 'repeat', getattr(schema_node, 'max_use', 1))
            logger.debug(f"{indent}Cursor={cursor} ('{current_segment.segment_id}'): Evaluating Schema Node='{schema_node.xid}' (Usage: {schema_node.usage}, Repeat: {repeat_val})")

            is_match = (isinstance(schema_node, StructureSegment) and current_segment.segment_id == schema_node.xid) or \
                       (isinstance(schema_node, StructureLoop) and self._get_starting_segment_id(schema_node) == current_segment.segment_id)

            if is_match:
                logger.debug(f"{indent}  -> MATCH FOUND.")
                max_repeats = schema_node.max_use if isinstance(schema_node, StructureSegment) else (99999 if not isinstance(schema_node.repeat, int) else schema_node.repeat)
                
                for i in range(max_repeats):
                    if cursor >= len(segments): break
                    
                    current_segment_for_repeat = segments[cursor]
                    repeat_match = (isinstance(schema_node, StructureSegment) and current_segment_for_repeat.segment_id == schema_node.xid) or \
                                   (isinstance(schema_node, StructureLoop) and self._get_starting_segment_id(schema_node) == current_segment_for_repeat.segment_id)

                    if not repeat_match:
                        expected_id = schema_node.xid if isinstance(schema_node, StructureSegment) else self._get_starting_segment_id(schema_node)
                        logger.debug(f"{indent}  -> Repeat loop for '{expected_id}' terminated. Next segment '{current_segment_for_repeat.segment_id}' does not match.")
                        break

                    if isinstance(schema_node, StructureSegment):
                        validation_errors = self.validator.validate(current_segment_for_repeat, schema_node.contextDefinitionId, depth + 1)
                        current_segment_for_repeat.errors.extend(validation_errors)
                        cdm_loop.segments.append(current_segment_for_repeat)
                        cursor += 1
                    elif isinstance(schema_node, StructureLoop):
                        sub_loop, segments_consumed = self._build_tree(segments[cursor:], schema_node.children, depth + 1, parent_loop_id=schema_node.xid)
                        cdm_loop.errors.extend(sub_loop.errors)
                        cdm_loop.add_loop(sub_loop)
                        cursor += segments_consumed
                
                schema_node_index += 1
            else: # No match
                if schema_node.usage == 'R':
                    error_msg = f"Required segment or loop '{schema_node.xid}' not found. Found '{current_segment.segment_id}' instead."
                    logger.debug(f"{indent}[FAIL] {error_msg}")
                    cdm_loop.errors.append(CdmValidationError(message=error_msg, line_number=current_segment.line_number, segment_id=current_segment.segment_id))
                    schema_node_index += 1
                else: # Situational ('S') node not found, advance schema and retry with same segment
                    logger.debug(f"{indent}  -> Skipping optional schema node '{schema_node.xid}'.")
                    schema_node_index += 1
                    
        finish_reason = "End of segments" if cursor >= len(segments) else "End of schema nodes"
        
        # After loop, check if any remaining required nodes were not met
        if schema_node_index < len(schema_nodes):
            finish_reason = "End of schema nodes"
            for i in range(schema_node_index, len(schema_nodes)):
                remaining_node = schema_nodes[i]
                if remaining_node.usage == 'R':
                    error_msg = f"Required segment or loop '{remaining_node.xid}' is missing at the end of its parent loop."
                    logger.debug(f"{indent}[FAIL] {error_msg}")
                    cdm_loop.errors.append(CdmValidationError(message=error_msg))
        
        logger.debug(f"{indent}[END LOOP PARSE: {parent_loop_id}] Consumed {cursor} segments. Reason: {finish_reason}.")
        return cdm_loop, cursor

    def _parse_transaction_set(self, segments: List[CdmSegment]) -> CdmTransaction:
        st_segment = segments[0]
        se_segment = segments[-1]
        transaction_body_segments = segments[1:-1]
        
        logger.debug("Attempting to find ST_LOOP in schema structure...")
        isa_loop = next((n for n in self.schema.structure if isinstance(n, StructureLoop) and n.xid == 'ISA_LOOP'), None)
        if not isa_loop or not isa_loop.children: raise ValueError("ISA_LOOP not found in schema structure")
        
        gs_loop = next((n for n in isa_loop.children if isinstance(n, StructureLoop) and n.xid == 'GS_LOOP'), None)
        if not gs_loop or not gs_loop.children: raise ValueError("GS_LOOP not found in schema structure")
        
        st_loop_schema = next((n for n in gs_loop.children if isinstance(n, StructureLoop) and n.xid == 'ST_LOOP'), None)
        if not st_loop_schema or not isinstance(st_loop_schema, StructureLoop):
            raise ValueError("ST_LOOP not found or is not a Loop in schema structure")
        
        st_loop_children = [child for child in st_loop_schema.children if child.xid not in ('ST', 'SE')]
        logger.debug("Found ST_LOOP. Parsing transaction body...")

        body_loop, consumed_count = self._build_tree(transaction_body_segments, st_loop_children, depth=1, parent_loop_id="ST_LOOP")

        transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
        transaction.errors.extend(body_loop.errors)

        if consumed_count != len(transaction_body_segments):
            error_line, error_seg_id = None, None
            if consumed_count < len(transaction_body_segments):
                problematic_segment = transaction_body_segments[consumed_count]
                error_line, error_seg_id = problematic_segment.line_number, problematic_segment.segment_id
            
            error_msg = f"Transaction parsing incomplete. Unexpected structure or missing mandatory segment at or before '{error_seg_id}' (line {error_line})."
            logger.warning(error_msg)
            transaction.errors.append(CdmValidationError(
                message=error_msg,
                line_number=error_line,
                segment_id=error_seg_id
            ))
        return transaction

    def parse(self) -> CdmInterchange:
        self.errors.clear()
        isa_idx = self._find_next_segment('ISA', self.all_segments, 0)
        iea_idx = self._find_next_segment('IEA', self.all_segments, isa_idx if isa_idx != -1 else 0)

        if isa_idx == -1 or iea_idx == -1:
            self.errors.append(CdmValidationError(message="ISA/IEA envelope not found."))
            dummy_isa = CdmSegment(segment_id='ISA', elements=[], line_number=0, raw_segment='')
            dummy_iea = CdmSegment(segment_id='IEA', elements=[], line_number=0, raw_segment='')
            return CdmInterchange(header=dummy_isa, trailer=dummy_iea, errors=self.errors)
        
        # --- THIS IS THE FIX ---
        # Validate the ISA and IEA segments after they are found.
        isa_segment = self.all_segments[isa_idx]
        iea_segment = self.all_segments[iea_idx]
        isa_segment.errors.extend(self.validator.validate(isa_segment))
        iea_segment.errors.extend(self.validator.validate(iea_segment))
        
        interchange = CdmInterchange(header=isa_segment, trailer=iea_segment)
        # --- END OF FIX ---
        
        group_segments = self.all_segments[isa_idx + 1:iea_idx]
        cursor = 0
        while cursor < len(group_segments):
            gs_idx = self._find_next_segment('GS', group_segments, cursor)
            if gs_idx == -1: break
            ge_idx = self._find_next_segment('GE', group_segments, gs_idx)
            if ge_idx == -1:
                interchange.errors.append(CdmValidationError(message=f"Unclosed functional group at line {group_segments[gs_idx].line_number}."))
                break

            # --- THIS IS THE FIX ---
            # Validate the GS and GE segments after they are found.
            gs_segment = group_segments[gs_idx]
            ge_segment = group_segments[ge_idx]
            gs_segment.errors.extend(self.validator.validate(gs_segment))
            ge_segment.errors.extend(self.validator.validate(ge_segment))
            
            func_group = CdmFunctionalGroup(header=gs_segment, trailer=ge_segment)
            # --- END OF FIX ---
            
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
        return interchange