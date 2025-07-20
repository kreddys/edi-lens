# FILE: backend/src/services/enrichment_service.py
import logging
import uuid
from typing import Dict, Any

from src.agents.crews import SchemaEnrichmentCrews
from src.agents.models import UniversalAgentResponse, AuditResponse
from src.utils.llm_output_parser import extract_json_from_llm_output
from crewai import Crew

logger = logging.getLogger(__name__)

# In-memory storage for job status and results.
# For a production system, this would be replaced with Redis or a database table.
job_storage: Dict[str, Dict[str, Any]] = {}

def run_enrichment_analysis(job_id: str, schema_name: str, segment_id: str, context_id: str):
    """
    The main function that will be run in the background.
    It executes the agent crew and stores the result.
    """
    try:
        logger.info(f"Starting enrichment analysis for job_id: {job_id}")
        job_storage[job_id] = {"status": "running", "result": None, "error": None}

        crews = SchemaEnrichmentCrews()
        
        # NOTE: For now, we are running a simplified, single-pass crew.
        # The full iterative process can be added back later if needed.
        architect_crew = Crew(agents=[crews.element_enrichment_agent_instance], tasks=[crews.element_enrichment_task()])
        
        inputs = {"segment_id": segment_id, "context_id": context_id}
        result = architect_crew.kickoff(inputs=inputs)
        
        if not result or not result.raw:
            raise ValueError("Agent crew returned an empty result.")

        json_output = extract_json_from_llm_output(result.raw)
        if not json_output:
            raise ValueError(f"Could not extract JSON from agent output: {result.raw}")

        response_model = UniversalAgentResponse.model_validate_json(json_output)
        
        logger.info(f"Successfully completed enrichment analysis for job_id: {job_id}")
        job_storage[job_id]["status"] = "complete"
        job_storage[job_id]["result"] = response_model.model_dump()

    except Exception as e:
        logger.error(f"Enrichment analysis failed for job_id: {job_id}. Error: {e}", exc_info=True)
        job_storage[job_id]["status"] = "failed"
        job_storage[job_id]["error"] = str(e)