# FILE: backend/services/enrichment_service.py
import logging
from crewai import Crew, Process
from pathlib import Path
from pydantic import ValidationError

from src.agents.crews import SchemaEnrichmentCrews
from src.agents.models import AuditResponse, UniversalAgentResponse
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

def validate_and_refine_proposal(proposal_json: str, crews_instance: SchemaEnrichmentCrews, original_inputs: dict, commit_dir: Path) -> UniversalAgentResponse:
    """Tries to validate a proposal. If it fails, it triggers the format correction loop."""
    try:
        validated_proposal = UniversalAgentResponse.model_validate_json(proposal_json)
        logger.info("  -> [Validation] Pydantic validation successful.")
        return validated_proposal
    except ValidationError as e:
        logger.warning("  -> [Validation] Pydantic validation failed. Triggering format correction task.")
        error_feedback = "\n".join([f"- At path `{' -> '.join(map(str, err['loc']))}`: {err['msg']}" for err in e.errors()])
        refinement_inputs = {**original_inputs, "previous_proposal": proposal_json, "validation_errors": error_feedback}
        
        format_correction_crew = crews_instance.format_correction_crew()
        log_path = commit_dir / "format_correction_run.log"
        correction_result = run_crew_with_file_logging(format_correction_crew, refinement_inputs, log_path)

        if not correction_result or not hasattr(correction_result, 'raw') or not correction_result.raw:
            return UniversalAgentResponse(reasoning="FATAL: Agent failed to produce output during format correction.", patches=[])
        
        corrected_json = extract_json_from_llm_output(correction_result.raw)
        if not corrected_json:
            return UniversalAgentResponse(reasoning="FATAL: Agent failed to produce valid JSON during format correction.", patches=[])

        try:
            final_proposal = UniversalAgentResponse.model_validate_json(corrected_json)
            logger.info("  -> [Validation] Format correction successful.")
            return final_proposal
        except ValidationError as final_e:
            logger.error(f"  -> [Validation] FATAL: Agent FAILED to correct formatting errors after retry.")
            return UniversalAgentResponse(reasoning=f"AGENT FAILED FORMAT CORRECTION. Final Errors:\n{final_e}", patches=[])

def run_segment_analysis(segment_id: str, context_id: str, schema_name: str, commit_dir: Path) -> UniversalAgentResponse:
    """Analyzes a single segment by invoking the full agent chain."""
    crews_instance = SchemaEnrichmentCrews()
    inputs = {"segment_id": segment_id, "context_id": context_id, "schema_name": schema_name}

    # Round 1: Architect
    architect_crew = crews_instance.architect_crew()
    logger.info("  -> [Agent Round 1] Architect is generating initial proposal...")
    architect_result = run_crew_with_file_logging(architect_crew, inputs, commit_dir / "round_1_architect.log")
    
    if not architect_result or not hasattr(architect_result, 'raw') or not architect_result.raw:
        return UniversalAgentResponse(reasoning="Architect failed to produce a result in Round 1. Check logs.", patches=[])
    
    initial_proposal_json = extract_json_from_llm_output(architect_result.raw)
    if not initial_proposal_json:
        return UniversalAgentResponse(reasoning="Architect failed to produce valid JSON in Round 1. Check logs.", patches=[])

    # Round 2: Structural Validation
    structurally_valid_proposal = validate_and_refine_proposal(initial_proposal_json, crews_instance, inputs, commit_dir)
    if "AGENT FAILED FORMAT CORRECTION" in structurally_valid_proposal.reasoning:
        return structurally_valid_proposal

    # Round 3: Auditor
    auditor_crew = crews_instance.auditor_crew()
    logger.info("  -> [Agent Round 3] Auditor is reviewing for logical correctness...")
    audit_result = run_crew_with_file_logging(auditor_crew, {"proposal": structurally_valid_proposal.model_dump_json()}, commit_dir / "round_3_auditor.log")
    
    if not audit_result or not hasattr(audit_result, 'raw') or not audit_result.raw:
        logger.warning("  -> Auditor agent failed to produce a result. Proceeding with architect's proposal.")
        return structurally_valid_proposal
    
    audit_response = AuditResponse.model_validate_json(extract_json_from_llm_output(audit_result.raw))

    if audit_response.approved:
        logger.info("  -> [Agent Verdict] Proposal APPROVED by auditor.")
        return structurally_valid_proposal

    # Round 4: Logical Refinement
    logger.warning(f"  -> [Agent Verdict] REJECTED by auditor. Reason: {audit_response.reasoning}. Starting logical refinement.")
    refinement_inputs = {**inputs, "previous_proposal": structurally_valid_proposal.model_dump_json(), "audit_feedback": audit_response.reasoning}
    refinement_crew = crews_instance.refinement_crew()
    logger.info("  -> [Agent Round 4] Architect is refining based on auditor feedback...")
    refined_result = run_crew_with_file_logging(refinement_crew, refinement_inputs, commit_dir / "round_4_refinement.log")
    
    if not refined_result or not hasattr(refined_result, 'raw') or not refined_result.raw:
        return structurally_valid_proposal
        
    refined_proposal_json = extract_json_from_llm_output(refined_result.raw)
    if not refined_proposal_json:
        return UniversalAgentResponse(reasoning="Architect failed to produce valid JSON during logical refinement.", patches=[])

    # Final Validation
    final_proposal = validate_and_refine_proposal(refined_proposal_json, crews_instance, inputs, commit_dir)
    return final_proposal

def run_human_refinement_analysis(segment_id: str, context_id: str, schema_name: str, previous_proposal: UniversalAgentResponse, user_feedback: str, repo_path: Path) -> UniversalAgentResponse:
    """Invokes the agent's refinement task with human feedback."""
    crews_instance = SchemaEnrichmentCrews()
    
    commit_dir = repo_path / "commits" / "_temp_refinement"

    refinement_inputs = {
        "segment_id": segment_id, "context_id": context_id, "schema_name": schema_name,
        "previous_proposal": previous_proposal.model_dump_json(),
        "user_feedback": user_feedback
    }
    
    refinement_crew = crews_instance.refinement_crew()
    log_file = commit_dir / "human_refinement.log"
    refined_result = run_crew_with_file_logging(refinement_crew, refinement_inputs, log_file)
    
    if not refined_result or not refined_result.raw:
        return UniversalAgentResponse(reasoning="Agent failed during human refinement.", patches=[])
    
    refined_proposal_json = extract_json_from_llm_output(refined_result.raw)
    if not refined_proposal_json:
        return UniversalAgentResponse(reasoning="Agent produced invalid JSON during human refinement.", patches=[])
        
    final_proposal = validate_and_refine_proposal(refined_proposal_json, crews_instance, refinement_inputs, commit_dir)
    return final_proposal