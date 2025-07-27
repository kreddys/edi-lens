# FILE: backend/src/core/edi_parser.py
import logging
import copy
from typing import List, Optional, Tuple, Dict, Any

from src.edi_schemas.edi_guide import ImplementationGuideSchema, StructureLoop, StructureSegment, StructureChild
from src.core.cdm import CdmInterchange, CdmFunctionalGroup, CdmTransaction, CdmLoop, CdmSegment, CdmElement, CdmValidationError

logger = logging.getLogger(__name__)

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
            for key, value in context_elements[el_xid].items():
                if value is not None:
                    effective["elements"][i][key] = value
    return effective

class SegmentValidator:
    def __init__(self, schema: ImplementationGuideSchema):
        self.schema = schema

    def validate(self, segment: CdmSegment, context_id: Optional[str] = None, depth=0) -> List[CdmValidationError]:
        indent = "  " * depth
        logger.debug(f"{indent}--- Starting validation for segment '{segment.segment_id}' (Context: {context_id or 'None'}) ---")
        errors: List[CdmValidationError] = []
        base_def_model = self.schema.segmentDefinitions.get(segment.segment_id)
        if not base_def_model:
            logger.warning(f"{indent}Validation FAILED: Base definition for '{segment.segment_id}' not found in schema.")
            return [CdmValidationError(message=f"Base definition for segment '{segment.segment_id}' not found in schema.")]
        
        base_def = base_def_model.model_dump(exclude_none=True)
        context_def_model = self.schema.contextualDefinitions.get(context_id) if context_id else None
        context_def = context_def_model.model_dump(exclude_none=True) if context_def_model else None
        
        effective_def = _get_effective_definition(base_def, context_def)
        logger.debug(f"{indent}Effective definition created. Validating {len(effective_def.get('elements', []))} elements.")
        
        elements_in_data = {el.position: el.value for el in segment.elements}

        for i, element_def in enumerate(effective_def.get("elements", [])):
            el_pos = i + 1
            el_xid = element_def.get("xid")
            
            is_present_in_data = el_pos in elements_in_data and elements_in_data[el_pos].strip() != ""
            
            if element_def.get("usage") == 'R' and not is_present_in_data:
                err_msg = f"Required element '{el_xid}' is missing."
                logger.debug(f"{indent}  [FAIL] {err_msg}")
                errors.append(CdmValidationError(message=err_msg))
                continue
            
            if not is_present_in_data:
                continue

            if "valid_codes" in element_def and element_def["valid_codes"]:
                allowed_codes = {str(code['code']) for code in element_def["valid_codes"]}
                value_in_data = elements_in_data[el_pos]
                if value_in_data not in allowed_codes:
                    err_msg = f"Element '{el_xid}' has an invalid value '{value_in_data}'. Allowed values are: {', '.join(sorted(list(allowed_codes)))}."
                    logger.debug(f"{indent}  [FAIL] {err_msg}")
                    errors.append(CdmValidationError(message=err_msg))
        
        logger.debug(f"{indent}--- Validation for '{segment.segment_id}' complete. Found {len(errors)} errors. ---")
        return errors

class EdiParser:
    def __init__(self, edi_string: str, schema: ImplementationGuideSchema):
        self.schema = schema
        self.validator = SegmentValidator(schema)
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
            elements = [CdmElement(value=val, position=i + 1) for i, val in enumerate(parts[1:])]
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

    def _build_tree(self, segments: List[CdmSegment], schema_nodes: List[StructureChild], depth=0) -> Tuple[CdmLoop, int]:
        indent = "  " * depth
        cdm_loop = CdmLoop(loop_id="level_content")
        cursor = 0
        schema_node_index = 0

        while schema_node_index < len(schema_nodes):
            if cursor >= len(segments):
                for i in range(schema_node_index, len(schema_nodes)):
                    remaining_node = schema_nodes[i]
                    if remaining_node.usage == 'R':
                        error_msg = f"Required segment or loop '{remaining_node.xid}' is missing at the end of its parent loop."
                        logger.debug(f"{indent}[FAIL] {error_msg}")
                        cdm_loop.errors.append(CdmValidationError(message=error_msg))
                break

            schema_node = schema_nodes[schema_node_index]
            current_segment = segments[cursor]
            
            logger.debug(f"{indent}Cursor {cursor} ('{current_segment.segment_id}'): Evaluating Schema Node '{schema_node.xid}' (Usage: {schema_node.usage})")

            is_match = (isinstance(schema_node, StructureSegment) and current_segment.segment_id == schema_node.xid) or \
                       (isinstance(schema_node, StructureLoop) and self._get_starting_segment_id(schema_node) == current_segment.segment_id)

            if is_match:
                logger.debug(f"{indent}  -> MATCH FOUND.")
                max_repeats = schema_node.max_use if isinstance(schema_node, StructureSegment) else 99999
                
                for i in range(max_repeats):
                    if cursor >= len(segments): break
                    
                    current_segment_for_repeat = segments[cursor]
                    repeat_match = (isinstance(schema_node, StructureSegment) and current_segment_for_repeat.segment_id == schema_node.xid) or \
                                   (isinstance(schema_node, StructureLoop) and self._get_starting_segment_id(schema_node) == current_segment_for_repeat.segment_id)

                    if not repeat_match: break

                    if isinstance(schema_node, StructureSegment):
                        validation_errors = self.validator.validate(current_segment_for_repeat, schema_node.contextDefinitionId, depth + 1)
                        current_segment_for_repeat.errors.extend(validation_errors)
                        cdm_loop.segments.append(current_segment_for_repeat)
                        cursor += 1
                    elif isinstance(schema_node, StructureLoop):
                        sub_loop, segments_consumed = self._build_tree(segments[cursor:], schema_node.children, depth + 1)
                        sub_loop.loop_id = schema_node.xid
                        cdm_loop.errors.extend(sub_loop.errors)
                        cdm_loop.add_loop(sub_loop)
                        cursor += segments_consumed
                
                schema_node_index += 1
            else: # No match
                if schema_node.usage == 'R':
                    error_msg = f"Required segment or loop '{schema_node.xid}' not found. Found '{current_segment.segment_id}' instead."
                    logger.debug(f"{indent}[FAIL] {error_msg}")
                    cdm_loop.errors.append(CdmValidationError(message=error_msg, line_number=current_segment.line_number, segment_id=current_segment.segment_id))
                    # DO NOT CONSUME THE SEGMENT. Just advance the schema pointer to see if the current segment matches the next rule.
                    schema_node_index += 1
                else: # Situational ('S') node not found
                    logger.debug(f"{indent}  -> Skipping optional schema node '{schema_node.xid}'.")
                    # DO NOT CONSUME THE SEGMENT. Just advance the schema pointer.
                    schema_node_index += 1
                    
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

        body_loop, consumed_count = self._build_tree(transaction_body_segments, st_loop_children, depth=1)
        body_loop.loop_id = "ST_LOOP"

        transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
        transaction.errors.extend(body_loop.errors)

        if consumed_count != len(transaction_body_segments):
            error_line, error_seg_id = None, None
            if consumed_count < len(transaction_body_segments):
                problematic_segment = transaction_body_segments[consumed_count]
                error_line, error_seg_id = problematic_segment.line_number, problematic_segment.segment_id
            
            error_msg = "Parser did not consume all segments in the transaction."
            logger.warning(f"{error_msg} Unconsumed segment starts at or near line {error_line} ('{error_seg_id}').")
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

        interchange = CdmInterchange(header=self.all_segments[isa_idx], trailer=self.all_segments[iea_idx])
        group_segments = self.all_segments[isa_idx + 1:iea_idx]
        cursor = 0
        while cursor < len(group_segments):
            gs_idx = self._find_next_segment('GS', group_segments, cursor)
            if gs_idx == -1: break
            ge_idx = self._find_next_segment('GE', group_segments, gs_idx)
            if ge_idx == -1:
                interchange.errors.append(CdmValidationError(message=f"Unclosed functional group at line {group_segments[gs_idx].line_number}."))
                break
            func_group = CdmFunctionalGroup(header=group_segments[gs_idx], trailer=group_segments[ge_idx])
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