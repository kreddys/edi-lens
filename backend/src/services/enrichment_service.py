# FILE: backend/services/enrichment_service.py
import logging
from pathlib import Path
from crewai import Crew

from src.agents.crews import SchemaEnrichmentCrews
from src.agents.models import UniversalAgentResponse
from src.utils.llm_output_parser import extract_json_from_llm_output

logger = logging.getLogger(__name__)

def run_crew_with_file_logging(crew: Crew, inputs: dict, log_file_path: Path) -> any:
    """
    Executes a crew while redirecting its verbose output to a specified log file.
    """
    # ... (logging setup is the same)
    crew_logger = logging.getLogger()
    original_level = crew_logger.level
    original_handlers = crew_logger.handlers[:]
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file_path, mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    crew_logger.setLevel(logging.INFO)
    crew_logger.handlers = [file_handler]

    result = None
    try:
        crew.verbose = True
        result = crew.kickoff(inputs=inputs)
    except Exception as e:
        # Log the exception to the file for posterity
        crew_logger.exception("An exception occurred during crew execution:")
        # Re-raise the exception so the main script stops and shows us the traceback
        raise e
    finally:
        # Restore original logging configuration
        crew_logger.setLevel(original_level)
        crew_logger.handlers = original_handlers
    
    return result

def run_segment_analysis(segment_id: str, context_id: str, schema_name: str, commit_dir: Path) -> UniversalAgentResponse:
    """
    Analyzes a single segment by invoking the Schema Architect agent directly.
    Logs the verbose output to a file.
    """
    logger.info("  -> Invoking Schema Architect Agent...")
    crews = SchemaEnrichmentCrews()
    architect_crew = Crew(
        agents=[crews.element_enrichment_agent_instance],
        tasks=[crews.element_enrichment_task()]
    )
    inputs = {"segment_id": segment_id, "context_id": context_id, "schema_name": schema_name}
    
    log_file = commit_dir / "architect.log"
    result = run_crew_with_file_logging(architect_crew, inputs, log_file)

    if not result or not result.raw:
        logger.error(f"  -> Agent failed to produce a result. See log: {log_file}")
        return UniversalAgentResponse(reasoning=f"Agent failed to produce a result. See log for details.", patches=[])

    json_output = extract_json_from_llm_output(result.raw)
    if not json_output:
        logger.error(f"  -> Agent failed to produce valid JSON. See log: {log_file}")
        return UniversalAgentResponse(reasoning=f"Agent failed to produce valid JSON. See log for details.", patches=[])
        
    try:
        response_model = UniversalAgentResponse.model_validate_json(json_output)
        return response_model
    except Exception as e:
        logger.error(f"  -> Pydantic validation failed for agent output. Error: {e}. See log: {log_file}")
        return UniversalAgentResponse(reasoning=f"Pydantic validation failed: {e}. See log for details.", patches=[])