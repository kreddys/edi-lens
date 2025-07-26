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

def finalize_commit(commit_dir: Path, repo_path: Path, previous_schema_path: Path, new_schema_dict: Dict, report_content: str):
    """Writes the final schema, report, and diff to a commit directory and updates HEAD."""
    # Write final schema and report
    with open(commit_dir / "schema.json", 'w') as f:
        json.dump(new_schema_dict, f, indent=2)
    with open(commit_dir / "report.md", 'w') as f:
        f.write(report_content)
    
    # Write final diff
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
            
    # Update HEAD symlink
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
    parser.add_argument("--repo-path", required=True, help="Path to the schema repository directory (relative to the project root).")
    parser.add_argument("--interactive", action="store_true", help="Default. Prompts for approval after each segment.")
    parser.add_argument("--non-interactive", dest='interactive', action='store_false', help="Runs in fully automated mode.")
    parser.set_defaults(interactive=True)
    args = parser.parse_args()
    
    project_root_in_container = Path(__file__).parent.parent
    repo_path = project_root_in_container / args.repo_path
    review_dir = project_root_in_container / "_review"

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
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_context = context_id.replace('.', '_').replace(':', '_')
        commit_name = f"{timestamp}_{segment_id}_{safe_context}"
        commit_dir = repo_path / "commits" / commit_name
        
        proposal_dict, validation_error = run_segment_analysis(segment_id, context_id, "in-memory-generation.json", commit_dir)
        
        # --- THIS IS THE CORRECTED INTERACTIVE LOOP ---
        interaction_in_progress = True
        while interaction_in_progress:
            if not proposal_dict:
                logger.info("  -> Agent returned no output. Skipping segment.")
                if commit_dir.exists(): shutil.rmtree(commit_dir)
                interaction_in_progress = False
                continue

            action = 'y'
            if args.interactive:
                if review_dir.exists(): shutil.rmtree(review_dir)
                review_dir.mkdir(parents=True, exist_ok=True)
                
                with open(review_dir / "agent_proposal.json", "w") as f: json.dump(proposal_dict, f, indent=2)
                
                logger.info(f"\n>>>> Changes proposed for '{segment_id}'. Please review the files in `_review/` <<<<")
                
                if validation_error:
                    logger.error("  -> 🚨 This proposal has STRUCTURE ERRORS and cannot be auto-applied.")
                    with open(review_dir / "validation_errors.txt", "w") as f: f.write(str(validation_error))
                    logger.error("     See `_review/validation_errors.txt` for details.")
                    action = input("Reject [n], Refine [r], Edit manually [e], Quit [q]? ").lower().strip()
                else:
                    action = input("Approve [y], Reject [n], Refine [r], Edit [e], Quit [q]? ").lower().strip()
            
            # --- Action Handling ---
            if action == 'y':
                if validation_error:
                    logger.error("  -> Cannot approve a proposal with validation errors. Please Edit [e] or Reject [n].")
                    continue # Stay in loop
                
                proposal_obj = UniversalAgentResponse.model_validate(proposal_dict)
                potential_next_schema = jsonpatch.apply_patch(dict(live_schema_dict), [p.model_dump(exclude_none=True) for p in proposal_obj.patches])
                commit_reason = "AI Proposal Approved"
                final_report = f"# Segment: ...\n\n**Commit Reason:** {commit_reason}\n\n**AI Reasoning:**\n> {proposal_obj.reasoning}"
                finalize_commit(commit_dir, current_schema_path, potential_next_schema, final_report)
                logger.info(f"  -> COMMITTED version {commit_name}.")
                interaction_in_progress = False
            
            elif action == 'n':
                logger.info(f"  -> REJECTED. The commit directory with logs is preserved for review.")
                interaction_in_progress = False

            elif action == 'r':
                feedback = input("Please provide refinement feedback for the agent: ")
                proposal_dict, validation_error = run_human_refinement_analysis(segment_id, context_id, "in-memory-generation.json", proposal_dict, feedback, commit_dir)
                # Loop continues to present the new proposal
            
            elif action == 'e':
                editable_file_path = review_dir / "agent_proposal.json"
                logger.info(f"--> Please FIX the errors or make changes in your IDE: {editable_file_path.relative_to(project_root_in_container)}")
                input("--> After saving your changes, press Enter here to continue...")
                try:
                    with open(editable_file_path, 'r') as f: user_edited_dict = json.load(f)
                    user_proposal = UniversalAgentResponse.model_validate(user_edited_dict)
                    potential_next_schema = jsonpatch.apply_patch(dict(live_schema_dict), [p.model_dump(exclude_none=True) for p in user_proposal.patches])
                    commit_reason = "User Manual Edit"
                    final_report = f"# Segment: ...\n\n**Commit Reason:** {commit_reason}\n\n**Original AI Reasoning:**\n> {user_proposal.reasoning}"
                    finalize_commit(commit_dir, current_schema_path, potential_next_schema, final_report)
                    logger.info(f"  -> COMMITTED version {commit_name}.")
                    interaction_in_progress = False
                except (ValidationError, json.JSONDecodeError, jsonpatch.JsonPatchException) as e:
                    logger.error(f"  -> ERROR: Your edited file is still invalid or could not be applied: {e}")
                    logger.warning("     The proposal will be shown again for you to fix.")
                    proposal_dict, validation_error = user_edited_dict, e
                    continue

            elif action == 'q':
                logger.info("Quitting generation process.")
                return
            
            else:
                logger.warning("Invalid option. Please try again.")

    if review_dir.exists():
        shutil.rmtree(review_dir)
    logger.info("✅ Schema generation process complete.")


if __name__ == "__main__":
    main()