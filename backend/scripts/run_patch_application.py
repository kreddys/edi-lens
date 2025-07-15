# FILE: backend/scripts/run_patch_application.py
import json
import logging
import argparse
from pathlib import Path
from jsonpatch import JsonPatch, JsonPatchException

# Basic logger setup
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

def apply_patches(run_directory: Path, output_file: Path):
    if not run_directory.is_dir():
        logger.error(f"Error: Run directory not found at '{run_directory}'")
        return

    original_schema_path = run_directory / "_original_schema_copy.json"
    patches_dir = run_directory / "proposed_patches"

    if not original_schema_path.exists() or not patches_dir.exists():
        logger.error("Error: Run directory is incomplete. Missing original schema or patches directory.")
        return

    with open(original_schema_path, 'r') as f:
        schema = json.load(f)
    
    logger.info("Starting patch application process...")
    
    applied_patches_count = 0
    for patch_file in sorted(patches_dir.glob("*.jsonpatch")):
        logger.info(f"Applying patch: {patch_file.name}")
        with open(patch_file, 'r') as f:
            patch = json.load(f)
        
        try:
            schema = JsonPatch(patch).apply(schema)
            applied_patches_count += 1
        except JsonPatchException as e:
            logger.error(f"Could not apply patch from {patch_file.name}: {e}")
            logger.error("Skipping this patch file.")
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(schema, f, indent=2)

    logger.info("---------------------------------")
    logger.info("Patch Application Complete!")
    logger.info(f"Applied patches from {applied_patches_count} files.")
    logger.info(f"Final enriched schema saved to: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply approved JSON patches to a schema.")
    parser.add_argument("run_directory", type=Path, help="The path to the 'enrichment_run_{timestamp}' directory.")
    parser.add_argument("output_file", type=Path, help="The path to save the final enriched schema file.")
    parser.add_argument("--approve", action="store_true", help="Mandatory flag to confirm patch application.")

    args = parser.parse_args()

    if not args.approve:
        logger.error("Missing --approve flag. This is a required safety measure to prevent accidental runs.")
        exit(1)
        
    apply_patches(args.run_directory, args.output_file)