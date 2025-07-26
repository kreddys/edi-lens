# FILE: backend/services/enrichment_service.py
import logging
import json
from crewai import Crew, Process
from pathlib import Path
from pydantic import ValidationError
from typing import Tuple, Optional, Dict

from src.agents.crews import SchemaEnrichmentCrews
from src.agents.models import UniversalAgentResponse
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

def run_segment_analysis(segment_id: str, context_id: str, schema_name: str, commit_dir: Path) -> Tuple[Optional[Dict], Optional[ValidationError]]:
    """
    Analyzes a single segment, validates the output, and returns both the
    raw proposal dictionary and any validation error that occurred.
    """
    crews_instance = SchemaEnrichmentCrews()
    inputs = {"segment_id": segment_id, "context_id": context_id, "schema_name": schema_name}

    architect_crew = crews_instance.architect_crew()
    logger.info("  -> [Agent] Architect is generating proposal...")
    architect_result = run_crew_with_file_logging(architect_crew, inputs, commit_dir / "architect.log")
    
    if not architect_result or not hasattr(architect_result, 'raw') or not architect_result.raw:
        return None, None
    
    proposal_json = extract_json_from_llm_output(architect_result.raw)
    if not proposal_json:
        return None, None
        
    try:
        validated_proposal = UniversalAgentResponse.model_validate_json(proposal_json)
        logger.info("  -> [Validation] Pydantic validation successful.")
        return validated_proposal.model_dump(), None
    except (ValidationError, json.JSONDecodeError) as e:
        logger.warning("  -> [Validation] Pydantic validation failed. Passing raw output to user for review.")
        try:
            raw_proposal_dict = json.loads(proposal_json)
            return raw_proposal_dict, e
        except json.JSONDecodeError:
            return {"raw_output": proposal_json}, e # Return raw string if it's not even JSON

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