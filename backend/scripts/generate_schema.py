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

from dotenv import load_dotenv

dotenv_path = Path(__file__).parent.parent.parent / '.env.dev'
load_dotenv(dotenv_path=dotenv_path)

from src.core.config import setup_logging
from src.core.schema_manager import schema_manager
from src.services.enrichment_service import run_segment_analysis
from src.edi_schemas.edi_guide import ImplementationGuideSchema
from src.agents.models import UniversalAgentResponse
from src.services.enrichment_service import run_segment_analysis 

setup_logging()
logger = logging.getLogger(__name__)


def get_latest_schema_path(repo_path: Path) -> Path:
    """Finds the path to the latest committed schema, or falls back to the base."""
    commits_dir = repo_path / "commits"
    base_schema_path = repo_path / "base" / "schema.json"
    if not commits_dir.exists() or not any(commits_dir.iterdir()):
        return base_schema_path
    latest_commit_dir = sorted(commits_dir.iterdir(), reverse=True)[0]
    return latest_commit_dir / "schema.json"

def create_permanent_commit(repo_path: Path, previous_schema_path: Path, new_schema_dict: Dict, report_content: str, commit_name: str):
    """Creates the final, permanent commit directory for an approved change."""
    commit_dir = repo_path / "commits" / commit_name
    commit_dir.mkdir(parents=True, exist_ok=True)
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
    diff = difflib.unified_diff(previous_content, new_content, fromfile=str(previous_schema_path), tofile=str(new_schema_path))
    with open(diff_path, 'w') as f_diff:
        f_diff.writelines(diff)

def run_human_refinement_analysis(segment_id: str, context_id: str, schema_name: str, previous_proposal: UniversalAgentResponse, user_feedback: str, commit_dir: Path) -> UniversalAgentResponse:
    """Invokes the agent's refinement task with human feedback."""
    from src.agents.crews import SchemaEnrichmentCrews
    from src.services.enrichment_service import run_crew_with_file_logging
    from src.utils.llm_output_parser import extract_json_from_llm_output
    from crewai import Crew
    logger.info("  -> [Human Refinement] Invoking agent with user feedback...")
    crews = SchemaEnrichmentCrews()
    refinement_inputs = {
        "segment_id": segment_id, "context_id": context_id, "schema_name": schema_name,
        "previous_proposal": previous_proposal.model_dump_json(),
        "user_feedback": user_feedback # Changed from audit_feedback
    }
    refinement_crew = Crew(agents=[crews.element_enrichment_agent_instance], tasks=[crews.refinement_task()])
    
    log_file = commit_dir / "human_refinement.log"
    refined_result = run_crew_with_file_logging(refinement_crew, refinement_inputs, log_file)
    
    if not refined_result or not refined_result.raw:
        return UniversalAgentResponse(reasoning="Agent failed during human refinement.", patches=[])
    
    refined_proposal_json = extract_json_from_llm_output(refined_result.raw)
    if not refined_proposal_json:
        return UniversalAgentResponse(reasoning="Agent produced invalid JSON during human refinement.", patches=[])
        
    return UniversalAgentResponse.model_validate_json(refined_proposal_json)


def main():
    parser = argparse.ArgumentParser(description="AI-Powered EDI Schema Version Control Generator")
    parser.add_argument("--repo-path", required=True, help="Path to the schema repository directory.")
    parser.add_argument("--interactive", action="store_true", help="Default. Prompts for approval after each segment with proposed changes.")
    parser.add_argument("--non-interactive", dest='interactive', action='store_false', help="Runs in fully automated mode.")
    parser.set_defaults(interactive=True)
    args = parser.parse_args()
    
    project_root_in_container = Path(__file__).parent.parent
    repo_path = project_root_in_container / args.repo_path
    
    def reload_schema_in_manager(schema_dict):
        try:
            schema_model = ImplementationGuideSchema.model_validate(schema_dict)
            schema_manager._schemas["in-memory-generation"] = schema_model
            schema_manager._schemas_by_filename["in-memory-generation.json"] = schema_model
            return schema_model
        except Exception as e:
            logger.error(f"Schema became invalid during generation: {e}")
            return None

    latest_schema_path = get_latest_schema_path(repo_path)
    if not latest_schema_path or not latest_schema_path.exists():
        logger.error(f"Could not find a base schema at '{repo_path / 'base' / 'schema.json'}'.")
        return
    
    with open(latest_schema_path, 'r') as f:
        schema_dict_for_tasks = json.load(f)
    
    schema = reload_schema_in_manager(schema_dict_for_tasks)
    if not schema: return
    
    tasks_to_run = schema.get_all_structured_segments()
    total_tasks = len(tasks_to_run)
    logger.info(f"Starting schema generation. Interactive mode: {'ON' if args.interactive else 'OFF'}")
    logger.info(f"Analyzing {total_tasks} unique segment contexts from latest schema '{latest_schema_path.relative_to(repo_path.parent)}'.")

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
        
        proposal = run_segment_analysis(segment_id, context_id, "in-memory-generation.json", commit_dir)
        
        interaction_complete = False
        while not interaction_complete:
            if not proposal or not proposal.patches:
                logger.info("  -> No changes proposed by AI. Cleaning up.")
                if commit_dir.exists():
                    shutil.rmtree(commit_dir)
                interaction_complete = True
                continue

            try:
                potential_next_schema = jsonpatch.apply_patch(dict(live_schema_dict), [p.model_dump(exclude_none=True) for p in proposal.patches])
            except jsonpatch.JsonPatchException as e:
                logger.error(f"  -> FAILED to apply patch for {segment_id}: {e}. Skipping.")
                interaction_complete = True
                continue

            if args.interactive:
                with open(commit_dir / "reasoning.md", "w") as f:
                    f.write(f"# AI Reasoning for `{segment_id}` in `{context_id}`\n\n{proposal.reasoning}")
                with open(commit_dir / "proposed_value.json", "w") as f:
                    json.dump(proposal.patches[0].value, f, indent=2)
                
                logger.info(f"\nChanges proposed for '{segment_id}'. Review artifacts and logs in:\n  -> {commit_dir}\n")
                action = input("Approve [y], Reject [n], Refine [r], Edit [e], Quit [q]? ").lower().strip()
            else:
                action = 'y'
            
            commit_reason, final_schema_to_commit = None, None

            if action == 'y':
                commit_reason, final_schema_to_commit = "AI Proposal Approved", potential_next_schema
                interaction_complete = True
            elif action == 'n':
                logger.info(f"  -> REJECTED. Discarding changes and deleting commit directory for {segment_id}.")
                shutil.rmtree(commit_dir)
                interaction_complete = True
                continue
            elif action == 'r':
                feedback = input("Please provide refinement feedback for the agent: ")
                proposal = run_human_refinement_analysis(segment_id, context_id, "in-memory-generation.json", proposal, feedback, commit_dir)
                continue
            elif action == 'e':
                editor = os.getenv('EDITOR', 'vim')
                editable_file_path = commit_dir / "proposed_value.json"
                logger.info(f"Opening '{editable_file_path}' in '{editor}'. Save and close to continue.")
                subprocess.run([editor, str(editable_file_path)])
                with open(editable_file_path, 'r') as f:
                    user_edited_value = json.load(f)
                
                user_patch = proposal.patches[0].model_copy(update={"value": user_edited_value})
                final_schema_to_commit = jsonpatch.apply_patch(dict(live_schema_dict), [user_patch.model_dump(exclude_none=True)])
                commit_reason = "User Manual Edit"
                interaction_complete = True
            elif action == 'q':
                logger.info("Quitting generation process. Deleting commit directory.")
                shutil.rmtree(commit_dir)
                return
            else:
                logger.warning("Invalid option. The proposal will be shown again.")
                continue

            # --- Finalize Commit Logic ---
            logger.info(f"  -> {commit_reason.upper()}. Finalizing commit for {segment_id}.")
            final_report = f"# Segment: `{segment_id}` (Context: `{context_id}`)\n\n**Commit Reason:** {commit_reason}\n\n**Original AI Reasoning:**\n> {proposal.reasoning.replace(chr(10), ' ')}"
            create_permanent_commit(repo_path, current_schema_path, final_schema_to_commit, final_report, commit_name)
            
            head_symlink = repo_path / "HEAD"
            new_schema_path = commit_dir / "schema.json"
            if head_symlink.is_symlink() or head_symlink.exists():
                head_symlink.unlink()
            head_symlink.symlink_to(new_schema_path)
            logger.info(f"  -> COMMITTED version {commit_name}.")

    logger.info("✅ Schema generation process complete.")

if __name__ == "__main__":
    main()