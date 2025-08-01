import json
import argparse
from pathlib import Path
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def add_identifiers_to_schema(input_path: Path, output_path: Path):
    """
    Reads a schema file, adds 'is_identifier: true' to the first element
    of all REF and DTP contextual definitions, and writes the result to a new file.
    """
    if not input_path.exists():
        logging.error(f"Input file not found: {input_path}")
        return

    logging.info(f"Reading schema from: {input_path}")
    with open(input_path, 'r') as f:
        schema_data = json.load(f)

    if "contextualDefinitions" not in schema_data:
        logging.error("No 'contextualDefinitions' key found in the schema.")
        return

    context_defs = schema_data["contextualDefinitions"]
    segments_to_modify = ("REF", "DTP")
    modified_count = 0

    logging.info(f"Searching for contexts involving segments: {', '.join(segments_to_modify)}...")

    for context_id, definition in context_defs.items():
        # Check if the context ID contains a target segment type (e.g., "2010AA.REF_TaxID")
        # This is a simple but effective way to find all relevant contexts.
        segment_type = context_id.split('.')[1].split('_')[0] if '.' in context_id else ''

        if segment_type in segments_to_modify:
            elements = definition.get("elements")
            if not elements or not isinstance(elements, dict):
                continue
            
            # The target element is always the first one, e.g., REF01, DTP01
            target_element_xid = f"{segment_type}01"

            if target_element_xid in elements:
                element_def = elements[target_element_xid]
                if not element_def.get("is_identifier"):
                    element_def["is_identifier"] = True
                    logging.info(f"  -> Added 'is_identifier' to {context_id} -> {target_element_xid}")
                    modified_count += 1

    logging.info(f"Total modifications made: {modified_count}")

    logging.info(f"Writing updated schema to: {output_path}")
    with open(output_path, 'w') as f:
        json.dump(schema_data, f, indent=2)
    
    logging.info("Script finished successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add 'is_identifier' flag to key elements in an EDI schema.")
    parser.add_argument(
        "--input-file",
        type=Path,
        required=True,
        help="Path to the input schema JSON file."
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        required=True,
        help="Path to write the modified schema JSON file."
    )
    args = parser.parse_args()
    
    add_identifiers_to_schema(args.input_file, args.output_file)