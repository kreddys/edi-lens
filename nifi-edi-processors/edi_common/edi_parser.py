# Enhanced EDI parser with full validation logic ported from backend/src/core/edi_parser.py
import logging
import re
import copy
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any, Union
from .cdm import CdmInterchange, CdmFunctionalGroup, CdmTransaction, CdmLoop, CdmSegment, CdmElement, CdmValidationError
from .edi_schema_models import ImplementationGuideSchema, StructureLoop, StructureSegment, StructureChild

logger = logging.getLogger(__name__)

# --- Validation Helpers (ported from backend) ---
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
        
        effective_def = self._get_effective_definition(base_def, context_def)
        elements_in_data = {el.position: el.value for el in segment.elements}

        for element_def in effective_def.get("elements", []):
            el_pos = element_def.get('seq')
            if not el_pos: continue
            value_in_data = elements_in_data.get(el_pos, "")
            errors.extend(self._validate_element_recursively(element_def, value_in_data, segment.segment_id, el_pos))
        
        errors.extend(self._validate_syntax_rules(segment, effective_def))
        return errors

    def _get_effective_definition(self, base_def: Dict[str, Any], context_def: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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
                
                # Only delete sub_elements if it exists in overrides
                if 'sub_elements' in overrides:
                    del overrides['sub_elements']

                for key, value in overrides.items():
                    if value is not None:
                        effective["elements"][i][key] = value
        return effective

    def _validate_element_recursively(self, element_def: Dict[str, Any], value: str, segment_id: str, position: int) -> List[CdmValidationError]:
        errors: List[CdmValidationError] = []
        
        # Handle usage requirement
        usage = element_def.get("usage", "N")
        if usage == "R" and not value:
            errors.append(CdmValidationError(
                message=f"Required element '{element_def.get('xid', f'{segment_id}{position:02d}')}' is missing.",
                line_number=None,
                segment_id=segment_id,
                element_xid=element_def.get("xid"),
                is_identifier_error=False
            ))
            return errors  # No point validating an empty required element further

        if not value:
            return errors  # Nothing more to validate for empty elements

        # Validate data type
        data_type = element_def.get("dataType")
        if data_type and not _validate_data_type(value, data_type):
            errors.append(CdmValidationError(
                message=f"Element '{element_def.get('xid', f'{segment_id}{position:02d}')}' value '{value}' is not a valid {data_type}.",
                line_number=None,
                segment_id=segment_id,
                element_xid=element_def.get("xid")
            ))

        # Validate length
        min_len = element_def.get("minLength")
        max_len = element_def.get("maxLength")
        if min_len is not None and len(value) < min_len:
            errors.append(CdmValidationError(
                message=f"Element '{element_def.get('xid', f'{segment_id}{position:02d}')}' value '{value}' is shorter than min length {min_len}.",
                line_number=None,
                segment_id=segment_id,
                element_xid=element_def.get("xid")
            ))
        if max_len is not None and len(value) > max_len:
            errors.append(CdmValidationError(
                message=f"Element '{element_def.get('xid', f'{segment_id}{position:02d}')}' value '{value}' is longer than max length {max_len}.",
                line_number=None,
                segment_id=segment_id,
                element_xid=element_def.get("xid")
            ))

        # Validate format
        data_format = element_def.get("format")
        if data_format and not _validate_format(value, data_format):
            errors.append(CdmValidationError(
                message=f"Element '{element_def.get('xid', f'{segment_id}{position:02d}')}' value '{value}' does not match expected format '{data_format}'.",
                line_number=None,
                segment_id=segment_id,
                element_xid=element_def.get("xid")
            ))

        # Validate codes
        valid_codes = element_def.get("valid_codes")
        if valid_codes and value:
            valid_code_values = [code_def.get("code") for code_def in valid_codes]
            if value not in valid_code_values:
                errors.append(CdmValidationError(
                    message=f"Element '{element_def.get('xid', f'{segment_id}{position:02d}')}' value '{value}' is not in the allowed code set {valid_code_values}.",
                    line_number=None,
                    segment_id=segment_id,
                    element_xid=element_def.get("xid")
                ))

        # Handle composite elements
        sub_elements = element_def.get("sub_elements")
        if sub_elements and data_type == "Composite":
            sub_values = value.split(self.component_separator)
            for i, sub_el_def in enumerate(sub_elements):
                sub_value = sub_values[i] if i < len(sub_values) else ""
                sub_errors = self._validate_element_recursively(sub_el_def, sub_value, segment_id, position)
                errors.extend(sub_errors)

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
        
        operator = clause["operator"]
        clause_value = clause.get("value", "")
        
        if operator == "IS":
            return value == clause_value
        elif operator == "IS_NOT":
            return value != clause_value
        elif operator == "IS_PRESENT":
            return bool(value)
        elif operator == "IS_NOT_PRESENT":
            return not bool(value)
        return False

    def _execute_assertion(self, segment: CdmSegment, assertion: Dict[str, Any], rule_id: str) -> List[CdmValidationError]:
        errors: List[CdmValidationError] = []
        assertion_type = assertion["assertion"]
        
        if assertion_type == "MUST_BE_FORMAT":
            element_ids = assertion.get("elements", [assertion.get("element")])
            format_value = assertion.get("value")
            for element_id in element_ids:
                if element_id:
                    pos = int(re.sub(r'\D', '', element_id))
                    value = segment.get_element(pos) or ""
                    if value and not _validate_format(value, format_value):
                        errors.append(CdmValidationError(
                            message=f"Element '{element_id}' value '{value}' does not match required format '{format_value}' (Rule: {rule_id}).",
                            line_number=segment.line_number,
                            segment_id=segment.segment_id,
                            element_xid=element_id
                        ))
        elif assertion_type == "MUST_HAVE_LENGTH":
            element_ids = assertion.get("elements", [assertion.get("element")])
            required_length = assertion.get("value")
            for element_id in element_ids:
                if element_id:
                    pos = int(re.sub(r'\D', '', element_id))
                    value = segment.get_element(pos) or ""
                    if len(value) != required_length:
                        errors.append(CdmValidationError(
                            message=f"Element '{element_id}' value '{value}' must have length {required_length} (Rule: {rule_id}).",
                            line_number=segment.line_number,
                            segment_id=segment.segment_id,
                            element_xid=element_id
                        ))
        elif assertion_type == "MUST_BE_PRESENT":
            element_ids = assertion.get("elements", [assertion.get("element")])
            for element_id in element_ids:
                if element_id:
                    pos = int(re.sub(r'\D', '', element_id))
                    value = segment.get_element(pos) or ""
                    if not value:
                        errors.append(CdmValidationError(
                            message=f"Element '{element_id}' must be present (Rule: {rule_id}).",
                            line_number=segment.line_number,
                            segment_id=segment.segment_id,
                            element_xid=element_id
                        ))
        elif assertion_type == "MUST_NOT_BE_PRESENT":
            element_ids = assertion.get("elements", [assertion.get("element")])
            for element_id in element_ids:
                if element_id:
                    pos = int(re.sub(r'\D', '', element_id))
                    value = segment.get_element(pos) or ""
                    if value:
                        errors.append(CdmValidationError(
                            message=f"Element '{element_id}' must not be present (Rule: {rule_id}).",
                            line_number=segment.line_number,
                            segment_id=segment.segment_id,
                            element_xid=element_id
                        ))
        elif assertion_type == "ANY_OF_MUST_BE_PRESENT":
            element_ids = assertion.get("elements", [])
            present_count = 0
            for element_id in element_ids:
                if element_id:
                    pos = int(re.sub(r'\D', '', element_id))
                    value = segment.get_element(pos) or ""
                    if value:
                        present_count += 1
            if present_count == 0:
                errors.append(CdmValidationError(
                    message=f"At least one of elements {element_ids} must be present (Rule: {rule_id}).",
                    line_number=segment.line_number,
                    segment_id=segment.segment_id
                ))
        
        return errors

class EdiParser:
    """
    Enhanced EDI parser with full validation logic.
    Ported from backend/src/core/edi_parser.py with NiFi-specific adaptations.
    """
    
    def __init__(self, edi_string: str, schema: Optional[ImplementationGuideSchema] = None):
        self.schema = schema
        self.errors: List[CdmValidationError] = []
        self.validator = SegmentValidator(schema, ':') if schema else None
        
        # Detect delimiters from the EDI string
        delims = self._detect_delimiters(edi_string)
        self.element_delimiter, self.segment_terminator, self.component_separator = delims
        
        # Update validator with correct component separator
        if self.validator:
            self.validator.component_separator = self.component_separator
        
        # Parse EDI string into segments
        self.all_segments: List[CdmSegment] = self._segmentize(edi_string)
        
        logger.debug(f"Parser initialized with {len(self.all_segments)} segments.")

    def _detect_delimiters(self, edi_string: str) -> Tuple[str, str, str]:
        """Detect EDI delimiters from the ISA segment."""
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

    def _segmentize(self, edi_string: str) -> List[CdmSegment]:
        """Parse EDI string into CdmSegment objects."""
        segments = []
        edi_content = edi_string.strip().replace('\r\n', '\n').replace('\r', '\n')
        
        if self.segment_terminator != '\n':
            edi_content = edi_content.replace('\n', '')
        
        raw_segments = edi_content.split(self.segment_terminator)
        
        for i, seg_str in enumerate(raw_segments):
            clean_seg = seg_str.strip()
            if not clean_seg:
                continue
            
            parts = clean_seg.split(self.element_delimiter)
            segment_id = parts[0]
            
            # Create CdmElement objects for each data element
            elements: List[CdmElement] = [
                CdmElement(value=value, position=idx + 1) 
                for idx, value in enumerate(parts[1:])
            ]

            segments.append(CdmSegment(
                segment_id=segment_id,
                elements=elements,
                line_number=i + 1,
                raw_segment=clean_seg
            ))
            
            # Stop at IEA segment
            if segment_id == 'IEA':
                break
                
        return segments
    
    def _find_next_segment(self, segment_id: str, segments: List[CdmSegment], start_index: int) -> int:
        """Find the next occurrence of a segment by ID."""
        for i in range(start_index, len(segments)):
            if segments[i].segment_id == segment_id:
                return i
        return -1
    
    def _get_starting_segment_id(self, node: StructureChild) -> Optional[str]:
        """Get the starting segment ID for a schema node."""
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
    ) -> Tuple[Optional[StructureChild], int]:
        """
        Finds the best schema node for the current data segment by performing trial validations.
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

            trial_errors = self.validator.validate(current_segment, context_id) if self.validator else []
            identifier_errors = [e for e in trial_errors if e.is_identifier_error]

            if not identifier_errors:
                logger.debug(f"               - Trial validation PASSED for node {i} ('{schema_node.xid}') with context '{context_id}'. This is the best match.")
                return schema_node, i
            else:
                logger.debug(f"               - Trial validation FAILED for node {i} ('{schema_node.xid}') with identifier errors: {[e.message for e in identifier_errors]}.")
                
        logger.debug(f"          -> No suitable match found for '{current_segment.segment_id}' in this loop.")
        return None, -1

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
                    if self.validator:
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

    def parse(self) -> CdmInterchange:
        """
        Parse the EDI document into a CdmInterchange structure with full validation.
        """
        self.errors.clear()
        
        # Find ISA and IEA segments
        isa_idx = self._find_next_segment('ISA', self.all_segments, 0)
        iea_idx = self._find_next_segment('IEA', self.all_segments, isa_idx if isa_idx != -1 else 0)

        if isa_idx == -1 or iea_idx == -1:
            self.errors.append(CdmValidationError(message="ISA/IEA envelope not found."))
            dummy_isa = CdmSegment(segment_id='ISA', elements=[], line_number=0, raw_segment='')
            dummy_iea = CdmSegment(segment_id='IEA', elements=[], line_number=0, raw_segment='')
            return CdmInterchange(header=dummy_isa, trailer=dummy_iea, errors=self.errors)
        
        # Get ISA and IEA segments
        isa_segment = self.all_segments[isa_idx]
        iea_segment = self.all_segments[iea_idx]
        
        # Create interchange
        interchange = CdmInterchange(header=isa_segment, trailer=iea_segment)
        
        # Parse functional groups
        group_segments = self.all_segments[isa_idx + 1:iea_idx]
        cursor = 0
        
        while cursor < len(group_segments):
            gs_idx = self._find_next_segment('GS', group_segments, cursor)
            if gs_idx == -1:
                break
                
            ge_idx = self._find_next_segment('GE', group_segments, gs_idx)
            if ge_idx == -1:
                interchange.errors.append(CdmValidationError(
                    message=f"Unclosed functional group at line {group_segments[gs_idx].line_number}."
                ))
                break

            gs_segment = group_segments[gs_idx]
            ge_segment = group_segments[ge_idx]
            
            func_group = CdmFunctionalGroup(header=gs_segment, trailer=ge_segment)
            
            # Parse transaction sets within this functional group
            transaction_segments = group_segments[gs_idx + 1:ge_idx]
            ts_cursor = 0
            
            while ts_cursor < len(transaction_segments):
                st_idx = self._find_next_segment('ST', transaction_segments, ts_cursor)
                if st_idx == -1:
                    break
                    
                se_idx = self._find_next_segment('SE', transaction_segments, st_idx)
                if se_idx == -1:
                    interchange.errors.append(CdmValidationError(
                        message=f"Unclosed transaction set at line {transaction_segments[st_idx].line_number}."
                    ))
                    break
                
                # Create transaction with parsed body
                st_segment = transaction_segments[st_idx]
                se_segment = transaction_segments[se_idx]
                
                # Parse transaction body with full tree structure if schema is available
                if self.schema:
                    try:
                        logger.info(f"=== PARSING TRANSACTION SET {st_segment.elements[1].value if len(st_segment.elements) > 1 else 'UNKNOWN'} ===")
                        
                        # Find ST_LOOP in schema structure
                        st_loop_schema = next((n for n in self.schema.structure if isinstance(n, StructureLoop) and n.xid == 'ST_LOOP'), None)
                        if not st_loop_schema:
                            # Try to find through ISA -> GS -> ST hierarchy
                            isa_loop = next((n for n in self.schema.structure if isinstance(n, StructureLoop) and n.xid == 'ISA_LOOP'), None)
                            if isa_loop and isa_loop.children:
                                gs_loop = next((n for n in isa_loop.children if isinstance(n, StructureLoop) and n.xid == 'GS_LOOP'), None)
                                if gs_loop and gs_loop.children:
                                    st_loop_schema = next((n for n in gs_loop.children if isinstance(n, StructureLoop) and n.xid == 'ST_LOOP'), None)
                        
                        if st_loop_schema:
                            # Get children excluding ST and SE
                            st_loop_children = [child for child in st_loop_schema.children if child.xid not in ('ST', 'SE')]
                            logger.info(f"Found ST_LOOP with {len(st_loop_children)} expected child structures")
                            
                            body_segments = transaction_segments[st_idx + 1:se_idx]
                            body_loop, consumed_count = self._build_tree(body_segments, st_loop_children, depth=1, parent_loop_id="ST_LOOP")
                            
                            transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
                            transaction.errors.extend(body_loop.errors)
                            
                            if consumed_count < len(body_segments):
                                unparsed_segments = body_segments[consumed_count:]
                                if unparsed_segments:
                                    problematic_segment = unparsed_segments[0]
                                    error_msg = f"Transaction parsing incomplete. Could not process {len(unparsed_segments)} remaining segments starting with '{problematic_segment.segment_id}' (line {problematic_segment.line_number})."
                                    logger.warning(error_msg)
                                    transaction.errors.append(CdmValidationError(
                                        message=error_msg, 
                                        line_number=problematic_segment.line_number, 
                                        segment_id=problematic_segment.segment_id
                                    ))
                        else:
                            # Fallback to simple parsing if no schema structure found
                            logger.warning("ST_LOOP not found in schema structure. Using simple parsing.")
                            body_segments = transaction_segments[st_idx + 1:se_idx]
                            body_loop = CdmLoop(loop_id="ST_LOOP")
                            body_loop.segments = body_segments
                            transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
                    except Exception as e:
                        logger.error(f"Critical error parsing transaction set: {str(e)}", exc_info=True)
                        # Create a minimal transaction with the error
                        body_loop = CdmLoop(loop_id="ST_LOOP")
                        transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
                        transaction.errors.append(CdmValidationError(
                            message=f"Critical parsing error: {str(e)}", 
                            line_number=st_segment.line_number, 
                            segment_id=st_segment.segment_id
                        ))
                else:
                    # Simple parsing without schema
                    body_segments = transaction_segments[st_idx + 1:se_idx]
                    body_loop = CdmLoop(loop_id="ST_LOOP")
                    body_loop.segments = body_segments
                    transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
                
                func_group.transactions.append(transaction)
                ts_cursor = se_idx + 1
            
            interchange.functional_groups.append(func_group)
            cursor = ge_idx + 1

        # Collect all errors for reporting
        all_errors = self._collect_all_errors(interchange)
        if all_errors:
            logger.warning(f"EDI parsing completed with {len(all_errors)} errors")
            for location, error in all_errors[:5]:  # Log first 5 errors
                logger.warning(f"  - {location}: {error.message}")
        else:
            logger.info("EDI parsing completed successfully with no errors")

        return interchange

    def _collect_all_errors(self, interchange: CdmInterchange) -> List[Tuple[str, CdmValidationError]]:
        """Collect all validation errors from the interchange."""
        all_errors: List[Tuple[str, CdmValidationError]] = []
        
        # Interchange errors
        for error in interchange.errors:
            all_errors.append(("Interchange", error))
        
        # Header/trailer errors
        for error in interchange.header.errors:
            all_errors.append(("ISA Header", error))
        for error in interchange.trailer.errors:
            all_errors.append(("IEA Trailer", error))
        
        # Functional group errors
        for group in interchange.functional_groups:
            for error in group.errors:
                all_errors.append(("Functional Group", error))
            for error in group.header.errors:
                all_errors.append(("GS Header", error))
            for error in group.trailer.errors:
                all_errors.append(("GE Trailer", error))
                
            # Transaction errors
            for transaction in group.transactions:
                for error in transaction.errors:
                    all_errors.append(("Transaction", error))
                for error in transaction.header.errors:
                    all_errors.append(("ST Header", error))
                for error in transaction.trailer.errors:
                    all_errors.append(("SE Trailer", error))
                    
                # Body loop errors (recursive)
                def collect_loop_errors(loop: CdmLoop, path: str = ""):
                    current_path = f"{path}.{loop.loop_id}" if path else loop.loop_id
                    for error in loop.errors:
                        all_errors.append((f"Loop {current_path}", error))
                    for segment in loop.segments:
                        for error in segment.errors:
                            all_errors.append((f"Segment {segment.segment_id} (Line: {segment.line_number})", error))
                    for loop_key, sub_loops in loop.loops.items():
                        for sub_loop in sub_loops:
                            collect_loop_errors(sub_loop, current_path)
                
                collect_loop_errors(transaction.body)
        
        return all_errors