# FILE: backend/scripts/review_schema.py
import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Set

from pydantic import ValidationError

# To run this script standalone, we need to add the project root to the path
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.edi_schemas.edi_guide import ImplementationGuideSchema, StructureChild, StructureSegment, StructureLoop

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class SchemaAnalyzer:
    def __init__(self, schema: ImplementationGuideSchema):
        self.schema = schema
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
        self.all_base_defs: Set[str] = set(self.schema.segmentDefinitions.keys())
        self.all_context_defs: Set[str] = set(self.schema.contextualDefinitions.keys())
        
        self.used_base_defs: Set[str] = set()
        self.used_context_defs: Set[str] = set()
        
        self.structure_report: List[str] = []
        self.contextualization_report: List[str] = []

    def analyze(self):
        logger.info("Starting schema analysis...")
        self._traverse_structure(self.schema.structure, 0)
        self._check_definition_usage()
        self._generate_contextualization_report()
        logger.info("Analysis complete.")

    def _traverse_structure(self, nodes: List[StructureChild], depth: int):
        indent = "  " * depth
        for node in nodes:
            if isinstance(node, StructureLoop):
                self.structure_report.append(f"{indent}LOOP: {node.xid} ({node.name}) - Repeat: {node.repeat}")
                if node.children:
                    self._traverse_structure(node.children, depth + 1)
            elif isinstance(node, StructureSegment):
                self.structure_report.append(f"{indent}SEGMENT: {node.xid} ({node.name}) - Max Use: {node.max_use}")
                self._validate_segment_links(node, f"{indent}  ")

    def _validate_segment_links(self, segment: StructureSegment, indent: str):
        # Check base definition link
        base_id = segment.segmentDefinitionId
        if base_id not in self.all_base_defs:
            self.errors.append(f"Structure Error: Segment '{segment.xid}' ('{segment.name}') links to a non-existent base definition '{base_id}'.")
        else:
            self.used_base_defs.add(base_id)
            self.structure_report.append(f"{indent}-> Links to Base Definition: '{base_id}' (OK)")
            
        # Check contextual definition link
        context_id = segment.contextDefinitionId
        if context_id:
            if context_id not in self.all_context_defs:
                self.errors.append(f"Structure Error: Segment '{segment.xid}' ('{segment.name}') links to a non-existent contextual definition '{context_id}'.")
            else:
                self.used_context_defs.add(context_id)
                self.structure_report.append(f"{indent}-> Links to Context Definition: '{context_id}' (OK)")

    def _check_definition_usage(self):
        unused_base = self.all_base_defs - self.used_base_defs
        if unused_base:
            for seg_id in sorted(list(unused_base)):
                self.warnings.append(f"Unused Definition: Base segment definition '{seg_id}' is defined but not used in the structure.")
                
        unused_context = self.all_context_defs - self.used_context_defs
        if unused_context:
            for seg_id in sorted(list(unused_context)):
                self.warnings.append(f"Unused Definition: Contextual definition '{seg_id}' is defined but not used in the structure.")

    def _generate_contextualization_report(self):
        self.contextualization_report.append("--- Contextualization Details ---")
        for context_id in sorted(list(self.used_context_defs)):
            context_def = self.schema.contextualDefinitions[context_id]
            
            base_seg_id_parts = context_def.id.split('.')
            # The part after the period is the potential base ID with a description
            potential_base_id_part = base_seg_id_parts[1] if len(base_seg_id_parts) > 1 else base_seg_id_parts[0]
            # The actual base ID is the part before the first underscore
            base_seg_id = potential_base_id_part.split('_')[0]
            
            if base_seg_id not in self.schema.segmentDefinitions:
                 self.contextualization_report.append(f"\nCONTEXT: {context_id} ('{context_def.name}') - ERROR: Could not find base segment '{base_seg_id}'.")
                 continue

            base_def = self.schema.segmentDefinitions[base_seg_id]
            base_elements = {el.xid: el for el in base_def.elements}

            self.contextualization_report.append(f"\nCONTEXT: {context_id} ('{context_def.name}')")
            self.contextualization_report.append(f"  Overrides base segment '{base_seg_id}':")

            # --- START OF FIX ---
            # Add a check to ensure context_def.elements is not None before iterating
            if context_def.elements:
                for el_xid, override in context_def.elements.items():
                    if el_xid not in base_elements:
                        self.warnings.append(f"Context '{context_id}' overrides non-existent element '{el_xid}' from base '{base_seg_id}'.")
                        continue
                    
                    base_el = base_elements[el_xid]
                    overrides_found = []
                    if override.usage and override.usage != base_el.usage:
                        overrides_found.append(f"Usage changed from '{base_el.usage}' to '{override.usage}'")
                    if override.name and override.name != base_el.name:
                         overrides_found.append(f"Name changed to '{override.name}'")
                    if override.valid_codes is not None:
                        overrides_found.append(f"Restricts valid codes")

                    # Only add the line if there are actual overrides to report
                    if overrides_found:
                        self.contextualization_report.append(f"    - Element '{el_xid}': {', '.join(overrides_found)}")
            else:
                self.contextualization_report.append("    (No element-specific overrides)")


    def print_summary(self):
        print("\n" + "="*80)
        print(" EDI Schema Analysis Report")
        print("="*80)
        
        if self.errors:
            print(f"\n❌ Found {len(self.errors)} FATAL ERROR(S):")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("\n✅ No fatal errors found. Schema links are valid.")
            
        if self.warnings:
            print(f"\n⚠️  Found {len(self.warnings)} WARNING(S):")
            for warning in self.warnings:
                print(f"  - {warning}")
        else:
            print("✅ No warnings found. All definitions are used.")
        
        print("\n" + "-"*80)
        for line in self.contextualization_report:
            print(line)
        
        print("\n" + "-"*80)
        print("--- Schema Structure Overview ---")
        for line in self.structure_report:
            print(line)
            
        print("\n" + "="*80)

def main():
    parser = argparse.ArgumentParser(description="Analyzes and validates an EDI implementation guide schema.")
    parser.add_argument("--schema-file", required=True, help="Path to the schema.json file to review.")
    args = parser.parse_args()
    
    schema_path = Path(args.schema_file)
    if not schema_path.is_file():
        logger.error(f"Schema file not found: {schema_path}")
        return

    logger.info(f"Loading and validating schema file: {schema_path}")
    
    try:
        with open(schema_path, 'r') as f:
            schema_data = json.load(f)
            schema = ImplementationGuideSchema.model_validate(schema_data)
        logger.info("Pydantic validation successful.")
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load or parse the schema file: {e}")
        return
        
    analyzer = SchemaAnalyzer(schema)
    analyzer.analyze()
    analyzer.print_summary()

if __name__ == "__main__":
    main()