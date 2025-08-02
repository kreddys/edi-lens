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

# Import the refactored helper function
from tests.agents.agent_test_utils import run_iterative_validation_process

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skip(reason="Skipping agent architecture tests as RAG/AI features are not currently active.")
]

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

# The run_iterative_validation_process function is removed from this file

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