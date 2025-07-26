# FILE: backend/scripts/generate_schema.py
import argparse
import json
import jsonpatch
import logging
import difflib
import subprocess
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict
from pydantic import ValidationError

# This script is designed to run inside a Docker container where the environment
# has already been configured by Docker Compose. It does not load .env files itself.
from src.core.config import setup_logging
from src.core.schema_manager import schema_manager
from src.services.enrichment_service import run_segment_analysis
from src.edi_schemas.edi_guide import ImplementationGuideSchema, SegmentDefinition
from src.agents.tools.schema_lookup import EDI_Schema_Lookup_Tool
from src.agents.tools.schema_structure import EDI_Schema_Structure_Tool

# Setup logging using settings loaded from the container's environment
setup_logging()
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def get_latest_schema_path(repo_path: Path) -> Path:
    """
    Finds the path to the latest valid schema.json file.
    It prioritizes the HEAD symlink, then falls back to chronological sort of commit directories,
    and finally falls back to the base schema.
    """
    head_symlink_path = repo_path / "HEAD"
    base_schema_path = repo_path / "base" / "schema.json"

    # --- FIX 1: Prioritize the HEAD symlink for resuming work ---
    if head_symlink_path.is_symlink():
        target_path = head_symlink_path.resolve()
        if target_path.exists() and target_path.is_file():
            logger.debug(f"Found latest schema via HEAD symlink: {target_path}")
            return target_path
        else:
            logger.warning(f"HEAD symlink at '{head_symlink_path}' is broken. Falling back to directory search.")

    commits_dir = repo_path / "commits"
    if commits_dir.exists():
        commit_dirs = [d for d in commits_dir.iterdir() if d.is_dir()]
        
        # --- FIX 2: Sort chronologically based on directory name ---
        # This is robust because the timestamp is at the beginning of the name.
        if commit_dirs:
            latest_commit_dir = max(commit_dirs, key=lambda d: d.name)
            potential_schema_path = latest_commit_dir / "schema.json"
            if potential_schema_path.is_file():
                logger.debug(f"Found latest schema by sorting commit directories: {potential_schema_path}")
                return potential_schema_path

    logger.debug(f"No valid commits found. Using base schema: {base_schema_path}")
    return base_schema_path

def finalize_commit(commit_dir: Path, repo_path: Path, previous_schema_path: Path, new_schema_dict: Dict, report_content: str):
    """Writes the final schema, report, and diff to a commit directory and updates HEAD."""
    with open(commit_dir / "schema.json", 'w') as f:
        json.dump(new_schema_dict, f, indent=2)
    with open(commit_dir / "report.md", 'w') as f:
        f.write(report_content)
    
    diff_path = commit_dir / "changes.diff"
    with open(previous_schema_path, 'r') as f_prev, open(commit_dir / "schema.json", 'r') as f_new:
        diff = difflib.unified_diff(
            f_prev.read().splitlines(keepends=True),
            f_new.read().splitlines(keepends=True),
            fromfile=str(previous_schema_path.relative_to(repo_path)),
            tofile=str((commit_dir / "schema.json").relative_to(repo_path)),
        )
        with open(diff_path, 'w') as f_diff:
            f_diff.writelines(diff)
            
    head_symlink = repo_path / "HEAD"
    new_schema_path = commit_dir / "schema.json"
    if head_symlink.is_symlink() or head_symlink.exists():
        head_symlink.unlink()
    head_symlink.symlink_to(new_schema_path.resolve())

def pre_flight_checks(repo_path: Path) -> bool:
    """Performs critical checks before starting the main generation loop."""
    logger.info("--- Running Pre-flight Checks ---")
    
    latest_schema_path = get_latest_schema_path(repo_path)
    if not latest_schema_path or not latest_schema_path.exists():
        logger.error(f"❌ PRE-FLIGHT CHECK FAILED: Base schema not found at '{repo_path / 'base' / 'schema.json'}'.")
        return False
    
    with open(latest_schema_path, 'r') as f:
        schema_dict = json.load(f)
    
    try:
        schema_manager._schemas_by_filename["in-memory-generation.json"] = ImplementationGuideSchema.model_validate(schema_dict)
        logger.info("✅ PRE-FLIGHT CHECK 1/3: Base schema loaded and validated successfully.")
    except Exception as e:
        logger.error(f"❌ PRE-FLIGHT CHECK FAILED: Base schema is invalid. Error: {e}")
        return False

    try:
        structure_tool = EDI_Schema_Structure_Tool()
        result_json = json.loads(structure_tool._run(segment_id="NM1"))
        if result_json.get("error"): raise RuntimeError(result_json["error"])
        logger.info("✅ PRE-FLIGHT CHECK 2/3: Schema Structure Tool executed successfully.")
    except Exception as e:
        logger.error(f"❌ PRE-FLIGHT CHECK FAILED: EDI_Schema_Structure_Tool failed. Error: {e}")
        return False

    try:
        lookup_tool = EDI_Schema_Lookup_Tool()
        result_json = json.loads(lookup_tool._run(segment_id="NM1", context_id="2010AA.NM1"))
        if result_json.get("error") is not None: raise RuntimeError(result_json["error"])
        logger.info("✅ PRE-FLIGHT CHECK 3/3: Schema Lookup Tool executed successfully.")
    except Exception as e:
        logger.error(f"❌ PRE-FLIGHT CHECK FAILED: EDI_Schema_Lookup_Tool failed. Error: {e}")
        return False
        
    logger.info("--- All Pre-flight Checks Passed ---\n")
    return True

def main():
    parser = argparse.ArgumentParser(description="AI-Powered EDI Schema Version Control Generator")
    parser.add_argument("--repo-path", required=True, help="Path to the schema repository directory (relative to the container's WORKDIR).")
    args = parser.parse_args()
    
    # --- THIS IS THE FIX ---
    # Resolve the repo_path to its full, absolute path inside the container immediately.
    # This ensures all subsequent path operations are consistent.
    repo_path = Path(args.repo_path).resolve()
    project_root_in_container = Path.cwd() # Should be /home/appuser/app
    # --- END OF FIX ---

    if not pre_flight_checks(repo_path):
        logger.error("Halting execution due to pre-flight check failures.")
        return
    
    def reload_schema_in_manager(schema_dict):
        try:
            schema_model = ImplementationGuideSchema.model_validate(schema_dict)
            schema_manager._schemas_by_filename["in-memory-generation.json"] = schema_model
            return schema_model
        except Exception as e:
            logger.error(f"Schema became invalid during generation: {e}")
            return None
    
    latest_schema_path = get_latest_schema_path(repo_path)
    with open(latest_schema_path, 'r') as f:
        schema_dict_for_tasks = json.load(f)
    
    schema = reload_schema_in_manager(schema_dict_for_tasks)
    if not schema: return

    logger.info("Inspecting commit history to determine resume point...")
    commits_dir = repo_path / "commits"
    completed_tasks = set()
    if commits_dir.exists():
        for commit_dir in commits_dir.iterdir():
            if commit_dir.is_dir():
                # Directory name is like: '20250726200956_ISA_loop_ISA'
                try:
                    # Name is like: 'TIMESTAMP_SEGMENTID_SAFE_CONTEXT'
                    parts = commit_dir.name.split('_', 2)
                    if len(parts) == 3:
                        _, segment_id, safe_context = parts
                        
                        # --- THIS IS THE DYNAMIC FIX ---
                        # Reconstruct the context_id to match the schema's logic.
                        # The schema generator uses 'loop:XID' for segments without a contextId,
                        # and these safe_context names will start with 'loop'.
                        # Otherwise, the original delimiter was a period.
                        if safe_context.startswith("loop"):
                            # Reconstruct 'loop:ISA' from 'loop_ISA'
                            context_id = safe_context.replace('_', ':', 1)
                        else:
                            # Reconstruct '2010AA.NM1' from '2010AA_NM1'
                            context_id = safe_context.replace('_', '.')
                        
                        completed_tasks.add((segment_id, context_id))
                        # --- END OF DYNAMIC FIX ---
                    else:
                         logger.warning(f"Could not parse commit directory name: {commit_dir.name}")
                except Exception as e:
                    logger.error(f"Error parsing commit directory '{commit_dir.name}': {e}")
    
    if completed_tasks:
        logger.info(f"Found {len(completed_tasks)} previously completed segments. They will be skipped.")    
    
    all_tasks = schema.get_all_structured_segments()
    tasks_to_run = [
        task for task in all_tasks 
        if (task['segment_id'], task['context_id']) not in completed_tasks
    ]

    total_tasks = len(tasks_to_run)
    logger.info("Starting schema generation...")
    logger.info(f"Analyzing {total_tasks} unique segment contexts from latest schema '{latest_schema_path.relative_to(project_root_in_container)}'.")

    for i, task in enumerate(tasks_to_run):
        current_schema_path = get_latest_schema_path(repo_path)
        with open(current_schema_path, 'r') as f:
            live_schema_dict = json.load(f)
        
        reload_schema_in_manager(live_schema_dict)
        
        segment_id, context_id = task['segment_id'], task['context_id']
        logger.info(f"[{i+1}/{total_tasks}] Analyzing segment '{segment_id}' in context '{context_id}'...")
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_context = context_id.replace('.', '_').replace(':', '_')
        commit_name = f"{timestamp}_{segment_id}_{safe_context}"
        commit_dir = repo_path / "commits" / commit_name
        commit_dir.mkdir(parents=True, exist_ok=True)
        
        agent_output_json_str = run_segment_analysis(segment_id, context_id, commit_dir)
        
        if not agent_output_json_str or agent_output_json_str == "{}":
            logger.warning(f"  -> Agent produced no output for {segment_id}. Please review logs and create the definition manually.")
            continue

        editable_file_path = commit_dir / "proposal.json"
        
        with open(editable_file_path, "w") as f:
            try:
                pretty_json = json.dumps(json.loads(agent_output_json_str), indent=2)
                f.write(pretty_json)
            except json.JSONDecodeError:
                f.write(agent_output_json_str)

        logger.info(f"\n>>>> ACTION REQUIRED for '{segment_id}' <<<<")
        logger.info(f"Please review and correct the agent's proposal in your IDE:")
        logger.info(f"  -> {editable_file_path.relative_to(project_root_in_container)}")
        logger.info(f"See agent logs in the same directory.")
        
        while True:
            action = input("Press Enter to APPLY your saved changes, or type [s] to SKIP, [q] to QUIT: ").lower().strip()
            
            if action == 's':
                logger.warning(f"  -> SKIPPED segment {segment_id}. The commit directory with artifacts is preserved for review.")
                break

            if action == 'q':
                logger.info("Quitting generation process.")
                return

            try:
                with open(editable_file_path, 'r') as f:
                    user_edited_dict = json.load(f)
                
                # --- THIS IS THE FIX ---
                # 1. Extract the actual segment definition from the agent's full response.
                # It's inside the 'value' of the first patch operation.
                if "patches" in user_edited_dict and len(user_edited_dict["patches"]) > 0:
                    segment_definition_to_validate = user_edited_dict["patches"][0].get("value")
                else:
                    raise ValueError("Proposal JSON is missing the 'patches' array or it is empty.")

                if not segment_definition_to_validate:
                     raise ValueError("The 'value' field within the first patch is missing or null.")

                # 2. Validate ONLY the extracted segment definition.
                SegmentDefinition.model_validate(segment_definition_to_validate)
                logger.info("  -> [Validation] Your edited proposal is valid.")
                
                # 3. Create the final patch using the full, user-edited structure.
                # This ensures the reasoning and correct patch path are preserved.
                patch = user_edited_dict.get("patches", [])
                if not patch:
                    raise ValueError("Could not create a valid patch from the proposal.")
                
                final_schema = jsonpatch.apply_patch(dict(live_schema_dict), patch)
                # --- END OF FIX ---
                
                final_report = f"# Segment: `{segment_id}` (Context: `{context_id}`)\n\n**Commit Reason:** Human Approved Edit\n\n"
                finalize_commit(commit_dir, repo_path, current_schema_path, final_schema, final_report)
                logger.info(f"  -> COMMITTED version {commit_name}.")
                break

            except (ValidationError, json.JSONDecodeError, jsonpatch.JsonPatchException, ValueError) as e:
                logger.error(f"  -> 🚨 ERROR: Your edited file is still invalid or could not be applied: {e}")
                logger.warning("     Please fix the file and press Enter to try again.")
    
    logger.info("✅ Schema generation process complete.")

if __name__ == "__main__":
    main()