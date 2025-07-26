# FILE: backend/services/enrichment_service.py
import logging
import json
from crewai import Crew, Process
from pathlib import Path
from pydantic import ValidationError
from typing import Tuple, Optional, Dict

from src.agents.crews import SchemaEnrichmentCrews
from src.agents.models import UniversalAgentResponse, AuditResponse
from src.utils.llm_output_parser import extract_json_from_llm_output

logger = logging.getLogger(__name__)

def run_crew_with_file_logging(crew: Crew, inputs: dict, log_file_path: Path) -> any:
    """Executes a crew while redirecting its verbose output to a specified log file."""
    crew_logger = logging.getLogger()
    original_level = crew_logger.level
    original_handlers = crew_logger.handlers[:]
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file_path, mode='w')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    
    crew_logger.setLevel(logging.INFO)
    crew_logger.handlers = [file_handler]

    result = None
    try:
        crew.verbose = True
        result = crew.kickoff(inputs=inputs)
    except Exception:
        crew_logger.exception("An exception occurred during crew execution:")
    finally:
        crew_logger.setLevel(original_level)
        crew_logger.handlers = original_handlers
    
    return result

def validate_and_refine_proposal(proposal_json: str, crews_instance: SchemaEnrichmentCrews, original_inputs: dict, commit_dir: Path) -> Tuple[Optional[Dict], Optional[ValidationError]]:
    """
    Tries to validate a proposal. If it fails, it triggers the format correction loop.
    Returns a tuple of (validated_proposal_dict, final_validation_error).
    """
    try:
        validated_proposal = UniversalAgentResponse.model_validate_json(proposal_json)
        logger.info("  -> [Validation] Pydantic validation successful.")
        return validated_proposal.model_dump(), None
    except (ValidationError, json.JSONDecodeError) as e:
        logger.warning(f"  -> [Validation] Pydantic validation failed: {e}. Triggering format correction task.")
        
        # We need to pass the raw text, not a formatted string of errors
        validation_error_str = str(e)
        
        refinement_inputs = {
            **original_inputs,
            "previous_proposal": proposal_json,
            "validation_errors": validation_error_str
        }
        
        format_correction_crew = crews_instance.format_correction_crew()
        log_path = commit_dir / "format_correction_run.log"
        correction_result = run_crew_with_file_logging(format_correction_crew, refinement_inputs, log_path)

        if not correction_result or not hasattr(correction_result, 'raw') or not correction_result.raw:
            return {"raw_output": "Agent failed to produce output during format correction."}, e

        corrected_json = extract_json_from_llm_output(correction_result.raw)
        if not corrected_json:
            return {"raw_output": correction_result.raw}, e

        try:
            final_proposal = UniversalAgentResponse.model_validate_json(corrected_json)
            logger.info("  -> [Validation] Format correction successful.")
            return final_proposal.model_dump(), None
        except (ValidationError, json.JSONDecodeError) as final_e:
            logger.error(f"  -> [Validation] FATAL: Agent FAILED to correct formatting errors after retry.")
            return json.loads(corrected_json), final_e

def run_segment_analysis(segment_id: str, context_id: str, commit_dir: Path) -> str:
    """
    Analyzes a single segment and returns the agent's raw JSON output as a string.
    """
    crews_instance = SchemaEnrichmentCrews()
    inputs = {"segment_id": segment_id, "context_id": context_id}

    architect_crew = Crew(
        agents=[crews_instance.element_enrichment_agent()],
        tasks=[crews_instance.element_enrichment_task()],
        process=Process.sequential
    )
    
    logger.info("  -> [Agent] Architect is generating proposal...")
    log_file = commit_dir / "architect.log"
    result = run_crew_with_file_logging(architect_crew, inputs, log_file)
    
    if not result or not hasattr(result, 'raw') or not result.raw:
        return "{}" # Return an empty JSON object on failure
    
    return extract_json_from_llm_output(result.raw)

def run_human_refinement_analysis(segment_id: str, context_id: str, schema_name: str, previous_proposal: dict, user_feedback: str, commit_dir: Path) -> Tuple[Optional[Dict], Optional[ValidationError]]:
    """Invokes the agent's refinement task with human feedback."""
    crews_instance = SchemaEnrichmentCrews()
    
    refinement_inputs = {
        "segment_id": segment_id, "context_id": context_id, "schema_name": schema_name,
        "previous_proposal": json.dumps(previous_proposal),
        "user_feedback": user_feedback
    }
    
    refinement_crew = crews_instance.refinement_crew()
    log_file = commit_dir / "human_refinement.log"
    refined_result = run_crew_with_file_logging(refinement_crew, refinement_inputs, log_file)
    
    if not refined_result or not refined_result.raw:
        return None, None
    
    refined_proposal_json = extract_json_from_llm_output(refined_result.raw)
    if not refined_proposal_json:
        return None, None
        
    try:
        validated_proposal = UniversalAgentResponse.model_validate_json(refined_proposal_json)
        logger.info("  -> [Validation] Refined proposal passed validation.")
        return validated_proposal.model_dump(), None
    except (ValidationError, json.JSONDecodeError) as e:
        logger.warning("  -> [Validation] Refined proposal also failed validation.")
        try:
            raw_proposal_dict = json.loads(refined_proposal_json)
            return raw_proposal_dict, e
        except json.JSONDecodeError:
            return {"raw_output": refined_proposal_json}, e