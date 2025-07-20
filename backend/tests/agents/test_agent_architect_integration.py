# FILE: backend/tests/agents/test_agent_architect_integration.py
import pytest
import os
import json
import logging
from unittest.mock import patch
from crewai import Crew
from crewai_tools import SerperDevTool
from pathlib import Path

from src.utils.telemetry import trace_crew
from src.utils.llm_output_parser import extract_json_from_llm_output
from src.agents.tools import KnowledgeBaseTool, EDI_Schema_Lookup_Tool
from src.agents.crews import SchemaEnrichmentCrews
from src.agents.models import AuditResponse, UniversalAgentResponse
from src.core.schema_manager import schema_manager
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]
logger = logging.getLogger(__name__)

@pytest.fixture(scope="module", autouse=True)
def check_llm_api_keys():
    api_keys_present = any([
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("OPENROUTER_API_KEY"),
        os.getenv("GROQ_API_KEY")
    ])
    if not api_keys_present:
        pytest.skip("Skipping agent tests: No LLM API key found in .env.test")

# The v2_schema_manager fixture is removed. The global schema_manager loaded by conftest is now the source of truth.

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
    logger.warning(f"--- VERDICT: REJECTED. REASON: {first_audit_response.justification}. STARTING REFINEMENT PASS. ---")
    refinement_inputs = {
        **inputs,
        "previous_proposal": initial_proposal_json,
        "audit_feedback": first_audit_response.justification
    }
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

def test_agent_uses_rag_first_for_contextual_override(check_llm_api_keys, async_client):
    # This test is now expected to pass.
    rag_response = "In the Subscriber Name loop (2010BA), the NM101 element must also accept the code 'QC' for patient relationships."
    with patch.object(KnowledgeBaseTool, '_run', return_value=rag_response):
        crews = SchemaEnrichmentCrews()
        response = run_iterative_validation_process(crews, {"segment_id": "NM1", "context_id": "2010BA.NM1"})
        assert response.approved is True, response.justification

def test_agent_uses_schema_lookup_and_proposes_no_change(check_llm_api_keys, async_client):
    # This test is correct.
    with patch.object(KnowledgeBaseTool, '_run', return_value="No new information found."):
        crews = SchemaEnrichmentCrews()
        response = run_iterative_validation_process(crews, {"segment_id": "CLM", "context_id": "2300.CLM"})
        assert response.approved is True, response.justification

def test_agent_uses_intrinsic_knowledge_when_schema_is_missing(check_llm_api_keys, async_client):
    # This test is correct.
    with patch.object(KnowledgeBaseTool, '_run', return_value="The CR1 segment is not mentioned."), \
         patch('src.agents.tools.schema_lookup.schema_manager.get_schema', return_value=None):
        crews = SchemaEnrichmentCrews()
        response = run_iterative_validation_process(crews, {"segment_id": "CR1", "context_id": "2300.CR1"})
        assert response.approved is True, response.justification

@pytest.mark.skip(reason="Tier 4 internet search is disabled for now.")
def test_agent_falls_back_to_internet_search(check_llm_api_keys, async_client):
    pass

def test_agent_synthesizes_rag_and_schema_info(check_llm_api_keys, async_client):
    # This test is now expected to pass.
    rag_response = "For the Submitter Contact (in loop 1000A), the PER02 (Name) element is required."
    with patch.object(KnowledgeBaseTool, '_run', return_value=rag_response):
        crews = SchemaEnrichmentCrews()
        response = run_iterative_validation_process(crews, {"segment_id": "PER", "context_id": "1000A.PER"})
        assert response.approved is True, response.justification

def test_agent_creates_contextual_override_not_base_change(check_llm_api_keys, async_client):
    # This test is now expected to pass.
    rag_response = "In the Payer Name loop (2010BB), the NM102 Entity Type Qualifier must be '2' for non-person payers."
    with patch.object(KnowledgeBaseTool, '_run', return_value=rag_response):
        crews = SchemaEnrichmentCrews()
        response = run_iterative_validation_process(crews, {"segment_id": "NM1", "context_id": "2010BB.NM1"})
        assert response.approved is True, response.justification

def test_agent_prioritizes_rag_over_base_schema(check_llm_api_keys, async_client):
    # This test is now expected to pass.
    rag_response = "For the Receiver's contact person, PER02 is Not Used."
    with patch.object(KnowledgeBaseTool, '_run', return_value=rag_response):
        crews = SchemaEnrichmentCrews()
        response = run_iterative_validation_process(crews, {"segment_id": "PER", "context_id": "1000B.PER"})
        assert response.approved is True, response.justification