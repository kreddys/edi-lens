# FILE: backend/tests/agents/agent_test_utils.py
import logging
from crewai import Crew

from src.agents.crews import SchemaEnrichmentCrews
from src.agents.models import AuditResponse
from src.utils.llm_output_parser import extract_json_from_llm_output
from src.utils.telemetry import trace_crew

logger = logging.getLogger(__name__)

def run_iterative_validation_process(crews: SchemaEnrichmentCrews, inputs: dict) -> AuditResponse:
    """
    Runs the full Architect -> Auditor -> (optional) Refinement -> final Auditor loop.
    Returns the final auditor's verdict.
    """
    # 1. First Pass: Architect generates the initial proposal
    architect_crew = Crew(agents=[crews.element_enrichment_agent_instance], tasks=[crews.element_enrichment_task()])
    logger.info("--- ARCHITECT: INITIAL PASS ---")
    architect_result = trace_crew(architect_crew, inputs)
    initial_proposal_json = extract_json_from_llm_output(architect_result.raw)
    
    # 2. First Audit: Auditor reviews the initial proposal
    auditor_crew = Crew(agents=[crews.auditor_agent_instance], tasks=[crews.audit_enrichment_task()])
    logger.info("--- AUDITOR: FIRST PASS ---")
    first_audit_result = trace_crew(auditor_crew, {"proposal": initial_proposal_json})
    first_audit_response = AuditResponse.model_validate_json(extract_json_from_llm_output(first_audit_result.raw))

    if first_audit_response.approved:
        logger.info("--- VERDICT: APPROVED ON FIRST PASS ---")
        return first_audit_response

    # 3. Refinement Pass (if first audit was rejected)
    # --- THIS IS THE FIX ---
    logger.warning(f"--- VERDICT: REJECTED. REASON: {first_audit_response.reasoning}. STARTING REFINEMENT PASS. ---")
    refinement_inputs = {
        **inputs,
        "previous_proposal": initial_proposal_json,
        "audit_feedback": first_audit_response.reasoning
    }
    # --- END OF FIX ---
    refinement_crew = Crew(agents=[crews.element_enrichment_agent_instance], tasks=[crews.refinement_task()])
    logger.info("--- ARCHITECT: REFINEMENT PASS ---")
    refined_result = trace_crew(refinement_crew, refinement_inputs)
    refined_proposal_json = extract_json_from_llm_output(refined_result.raw)

    # 4. Final Audit: Auditor reviews the refined proposal
    logger.info("--- AUDITOR: FINAL PASS ---")
    final_audit_result = trace_crew(auditor_crew, {"proposal": refined_proposal_json})
    final_audit_response = AuditResponse.model_validate_json(extract_json_from_llm_output(final_audit_result.raw))
    
    logger.info(f"--- FINAL VERDICT: {'APPROVED' if final_audit_response.approved else 'REJECTED'}")
    return final_audit_response