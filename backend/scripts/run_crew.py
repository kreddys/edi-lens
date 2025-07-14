# FILE: backend/scripts/run_crew.py
import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- Step 1: Set up project path and LOAD THE ENVIRONMENT ---
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

env_path = project_root.parent / ".env.local" 
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# --- Step 2: Now, import application modules ---
from src.core.config import settings, setup_logging
import openlit

# Import the new engine and its models
from src.refinement_engine.engine import SchemaRefinementEngine
from src.refinement_engine.models import KnowledgeSource

# --- Step 3: Configure Logging & OpenLIT ---
setup_logging()
logger = logging.getLogger(__name__)

if os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true":
    logger.info("Observability is enabled. Initializing OpenLIT...")
    openlit.init(application_name="edi-lens-crew")
else:
    logger.info("Observability is disabled.")


def run_full_schema_refinement():
    """
    A command-line interface for the SchemaRefinementEngine.
    This function orchestrates the entire "Plan & Execute" workflow.
    """
    logger.info("--- EDI Lens Schema Refinement Utility ---")
    
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OLLAMA_BASE_URL"):
        logger.error("No LLM API key or configuration found.")
        logger.error("Please ensure the required API key for your chosen provider is set in your .env.local file.")
        return

    # --- Define Inputs ---
    # For this test, we'll use a placeholder text file for the knowledge source.
    # In a real scenario, this would point to a PDF or DOCX file.
    knowledge_dir = project_root / "data" / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    knowledge_file = knowledge_dir / "X222A1_guide.txt"
    knowledge_file.write_text(
        "This is the implementation guide for 837P X222A1. "
        "Rule 1: The CLM segment is for claim level data. Its CLM02 element for total claim charge must be required. "
        "Rule 2: The NM1 segment in the 2010AA loop is for the Billing Provider. The NM109 element must be required."
    )

    # We'll use the sample schema as our base for refinement.
    base_schema_path = project_root.parent / "docs" / "schema" / "sample_schema.json"
    output_schema_path = project_root / "data" / "schemas_refined" / "sample_schema.refined.json"
    output_schema_path.parent.mkdir(exist_ok=True)

    with open(base_schema_path, 'r') as f:
        base_schema = json.load(f)

    knowledge = KnowledgeSource(source_type="file", content=str(knowledge_file))
    
    # --- Initialize and Run the Engine ---
    engine = SchemaRefinementEngine(base_schema=base_schema, knowledge_source=knowledge)
    
    for status in engine.run():
        progress_bar = ""
        if status.progress is not None:
            filled_len = int(40 * status.progress)
            progress_bar = f"[{'=' * filled_len}{' ' * (40 - filled_len)}]"
        
        logger.info(f"[{status.phase.upper():<9}] {progress_bar} {status.message}")
        
        if status.details:
            logger.debug(json.dumps(status.details, indent=2))
        
        if status.phase == "Failed":
            logger.error("Refinement stopped due to an unrecoverable error.")
            return

    # --- Finalization ---
    if status.phase == "Complete":
        logger.info("Refinement complete. Saving final schema...")
        final_schema = engine.get_final_schema()
        with open(output_schema_path, 'w') as f:
            json.dump(final_schema, f, indent=2)
            
        logger.info(f"✅ Final schema saved to {output_schema_path}")

if __name__ == "__main__":
    run_full_schema_refinement()