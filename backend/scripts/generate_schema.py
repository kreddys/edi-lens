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

# This script is designed to run inside a Docker container where the environment
# has already been configured by Docker Compose. It does not load .env files itself.
from src.core.config import setup_logging
from src.core.schema_manager import schema_manager
from src.services.enrichment_service import run_segment_analysis, run_human_refinement_analysis
from src.edi_schemas.edi_guide import ImplementationGuideSchema
from src.agents.models import UniversalAgentResponse
from src.agents.tools.schema_lookup import EDI_Schema_Lookup_Tool
from src.agents.tools.schema_structure import EDI_Schema_Structure_Tool

# Setup logging using settings loaded from the container's environment
setup_logging()
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def get_latest_schema_path(repo_path: Path) -> Path:
    """
    Finds the path to the latest valid schema.json file.
    It searches commits in reverse chronological order and falls back to the base schema.
    """
    commits_dir = repo_path / "commits"
    base_schema_path = repo_path / "base" / "schema.json"

    if commits_dir.exists():
        sorted_commits = [d for d in commits_dir.iterdir() if d.is_dir()]
        sorted_commits.sort(reverse=True)
        for commit_dir in sorted_commits:
            potential_schema_path = commit_dir / "schema.json"
            if potential_schema_path.is_file():
                return potential_schema_path

    return base_schema_path

def finalize_commit(commit_dir: Path, previous_schema_path: Path, new_schema_dict: Dict, report_content: str):
    """Writes the final schema, report, and diff to a commit directory."""
    new_schema_path = commit_dir / "schema.json"
    with open(new_schema_path, 'w') as f:
        json.dump(new_schema_dict, f, indent=2)

    report_path = commit_dir / "report.md"
    with open(report_path, 'w') as f:
        f.write(report_content)
    
    diff_path = commit_dir / "changes.diff"
    with open(previous_schema_path, 'r') as f_prev:
        previous_content = f_prev.read().splitlines(keepends=True)
    with open(new_schema_path, 'r') as f_new:
        new_content = f_new.read().splitlines(keepends=True)
    diff = difflib.unified_diff(
        previous_content, 
        new_content, 
        fromfile=str(previous_schema_path.name), 
        tofile=str(new_schema_path.name)
    )
    with open(diff_path, 'w') as f_diff:
        f_diff.writelines(diff)

def pre_flight_checks(repo_path: Path) -> bool:
    """
    Performs critical checks before starting the main generation loop.
    Returns True if all checks pass, False otherwise.
    """
    logger.info("--- Running Pre-flight Checks ---")
    
    latest_schema_path = get_latest_schema_path(repo_path)
    if not latest_schema_path or not latest_schema_path.exists():
        logger.error(f"❌ PRE-FLIGHT CHECK FAILED: Base schema not found at '{repo_path / 'base' / 'schema.json'}'.")
        return False
    
    with open(latest_schema_path, 'r') as f:
        schema_dict = json.load(f)
    
    try:
        schema_model = ImplementationGuideSchema.model_validate(schema_dict)
        # --- THIS IS THE FIX ---
        # Use the SAME key that the main process and tools will use.
        schema_manager._schemas_by_filename["in-memory-generation.json"] = schema_model
        logger.info("✅ PRE-FLIGHT CHECK 1/3: Base schema loaded and validated successfully.")
    except Exception as e:
        logger.error(f"❌ PRE-FLIGHT CHECK FAILED: Base schema is invalid. Error: {e}")
        return False

    try:
        structure_tool = EDI_Schema_Structure_Tool()
        result_str = structure_tool._run(segment_id="NM1")
        result_json = json.loads(result_str)
        if result_json.get("error"):
            raise RuntimeError(result_json["error"])
        logger.info("✅ PRE-FLIGHT CHECK 2/3: Schema Structure Tool executed successfully.")
    except Exception as e:
        logger.error(f"❌ PRE-FLIGHT CHECK FAILED: EDI_Schema_Structure_Tool failed. Error: {e}")
        return False

    try:
        lookup_tool = EDI_Schema_Lookup_Tool()
        result_str = lookup_tool._run(segment_id="NM1", context_id="2010AA.NM1")
        result_json = json.loads(result_str)
        if result_json.get("error") is not None:
            raise RuntimeError(result_json["error"])
        logger.info("✅ PRE-FLIGHT CHECK 3/3: Schema Lookup Tool executed successfully.")
    except Exception as e:
        logger.error(f"❌ PRE-FLIGHT CHECK FAILED: EDI_Schema_Lookup_Tool failed. Error: {e}")
        return False
        
    logger.info("--- All Pre-flight Checks Passed ---\n")
    return True

def main():
    parser = argparse.ArgumentParser(description="AI-Powered EDI Schema Version Control Generator")
    parser.add_argument("--repo-path", required=True, help="Path to the schema repository directory (relative to project root).")
    parser.add_argument("--interactive", action="store_true", help="Default. Prompts for approval after each segment.")
    parser.add_argument("--non-interactive", dest='interactive', action='store_false', help="Runs in fully automated mode.")
    parser.set_defaults(interactive=True)
    args = parser.parse_args()
    
    project_root_in_container = Path(__file__).parent.parent
    repo_path = project_root_in_container / args.repo_path

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
    
    tasks_to_run = schema.get_all_structured_segments()
    total_tasks = len(tasks_to_run)
    logger.info(f"Starting schema generation. Interactive mode: {'ON' if args.interactive else 'OFF'}")
    logger.info(f"Analyzing {total_tasks} unique segment contexts from latest schema '{latest_schema_path.relative_to(project_root_in_container)}'.")

    for i, task in enumerate(tasks_to_run):
        current_schema_path = get_latest_schema_path(repo_path)
        with open(current_schema_path, 'r') as f:
            live_schema_dict = json.load(f)
        
        reload_schema_in_manager(live_schema_dict)
        
        segment_id, context_id = task['segment_id'], task['context_id']
        logger.info(f"[{i+1}/{total_tasks}] Analyzing segment '{segment_id}' in context '{context_id}'...")
        
        # --- NEW LOGIC: Create the commit directory upfront to store all artifacts ---
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_context = context_id.replace('.', '_').replace(':', '_')
        commit_name = f"{timestamp}_{segment_id}_{safe_context}"
        commit_dir = repo_path / "commits" / commit_name
        
        proposal = run_segment_analysis(segment_id, context_id, "in-memory-generation.json", commit_dir)
        
        while True:
            if not proposal or not proposal.patches:
                logger.info("  -> No changes proposed by AI. Cleaning up temporary artifacts.")
                if commit_dir.exists(): shutil.rmtree(commit_dir)
                break

            try:
                potential_next_schema = jsonpatch.apply_patch(dict(live_schema_dict), [p.model_dump(exclude_none=True) for p in proposal.patches])
            except jsonpatch.JsonPatchException as e:
                logger.error(f"  -> FAILED to apply patch for {segment_id}: {e}. Skipping.")
                break

            action = 'y'
            if args.interactive:
                with open(commit_dir / "reasoning.md", "w") as f: f.write(f"# AI Reasoning\n\n{proposal.reasoning}")
                with open(commit_dir / "proposed_value.json", "w") as f: json.dump(proposal.patches[0].value, f, indent=2)
                
                logger.info(f"\nChanges proposed for '{segment_id}'. Please review the files and logs in:\n  -> {commit_dir}\n")
                action = input("Approve [y], Reject [n], Refine [r], Edit [e], Quit [q]? ").lower().strip()
            
            commit_reason, final_schema_to_commit = None, None

            if action == 'y' or action == 'e':
                commit_reason = "AI Proposal Approved"
                final_schema_to_commit = potential_next_schema
                
                if action == 'e':
                    editable_file_path = commit_dir / "proposed_value.json"
                    logger.info(f"--> Please edit this file now in your IDE: {editable_file_path.relative_to(project_root_in_container)}")
                    input("--> After saving your changes, press Enter here to continue...")
                    try:
                        with open(editable_file_path, 'r') as f: user_edited_value = json.load(f)
                        user_patch = proposal.patches[0].model_copy(update={"value": user_edited_value})
                        final_schema_to_commit = jsonpatch.apply_patch(dict(live_schema_dict), [user_patch.model_dump(exclude_none=True)])
                        commit_reason = "User Manual Edit"
                    except Exception as e:
                        logger.error(f"  -> ERROR processing edited file: {e}. The proposal will be shown again.")
                        continue

                final_report = f"# Segment: `{segment_id}` (Context: `{context_id}`)\n\n**Commit Reason:** {commit_reason}\n\n**Original AI Reasoning:**\n> {proposal.reasoning.replace(chr(10), ' ')}"
                
                finalize_commit(commit_dir, current_schema_path, final_schema_to_commit, final_report)
                
                head_symlink = repo_path / "HEAD"
                new_schema_path = commit_dir / "schema.json"
                if head_symlink.is_symlink() or head_symlink.exists():
                    head_symlink.unlink()
                head_symlink.symlink_to(new_schema_path.resolve())
                logger.info(f"  -> COMMITTED version {commit_name}.")
                break

            elif action == 'n':
                logger.info(f"  -> REJECTED. Discarding changes for {segment_id}. The commit directory with logs is preserved for review.")
                # We no longer delete the directory, it becomes a record of a rejected change
                # To re-run, the user would manually delete this folder.
                break
            
            elif action == 'r':
                feedback = input("Please provide refinement feedback for the agent: ")
                proposal = run_human_refinement_analysis(segment_id, context_id, "in-memory-generation.json", proposal, feedback, commit_dir)
            
            elif action == 'q':
                logger.info("Quitting generation process. The last proposed change directory is preserved for review.")
                return
            
            else:
                logger.warning("Invalid option. Please try again.")

    logger.info("✅ Schema generation process complete.")

if __name__ == "__main__":
    main()