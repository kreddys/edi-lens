import os
import json
import logging
from pathlib import Path

# --- Setup Project Path ---
project_root = Path(__file__).parent.parent
import sys
sys.path.append(str(project_root))
# --- End Setup ---

# Must import config and setup logging BEFORE other project modules.
# Pydantic's Settings class will now automatically find and load the .env files.
from src.core.config import settings, setup_logging
from src.core.schema_manager import schema_manager
from src.agents.crew import create_schema_refinement_crew

# --- Setup Logging ---
# This will configure the root logger based on LOG_LEVEL in your .env file
setup_logging()
logger = logging.getLogger(__name__)


def run_test():
    """Initializes and runs the schema refinement crew."""
    logger.info("--- Starting Schema Refinement Crew ---")

    # The .env files are now loaded automatically by the Settings class.
    # We just need to check if the required API key is present.
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OLLAMA_BASE_URL"):
        logger.error("No LLM API key or configuration found.")
        logger.error("Please ensure the required API key for your chosen provider is set in your .env.local file.")
        return

    # 2. Initialize the Schema Manager to load schemas into memory
    # We replace the hardcoded path from the Docker container with the local equivalent
    local_schema_path = str(project_root) + settings.EDI_SCHEMA_DIRECTORY.replace('/home/appuser/app', '')
    schema_dir = Path(local_schema_path)

    logger.info(f"Loading schemas from local path: {schema_dir}")
    schema_manager.load_schemas(schema_dir)
    logger.debug(f"Loaded schemas: {list(schema_manager._schemas.keys())}")

    # 3. Define the user's request
    schema_to_edit = '005010X222A1'
    
    # --- Try different inputs here ---
    user_query = """
    In our implementation guide for the 837P, the claim information loop (2300)
    requires a Payer Claim Control Number. This should be sent in a REF segment
    with an 'F8' qualifier. This entire REF segment should be mandatory.
    """
    
    # user_query = "The subscriber's name in loop 2010BA is required."

    logger.info("--- User Query ---")
    logger.info(user_query)
    logger.info("--------------------")

    # 4. Create and run the crew
    crew = create_schema_refinement_crew(schema_name=schema_to_edit, user_input=user_query)
    
    logger.info("🚀 Kicking off the crew...")
    result = crew.kickoff()

    logger.info("--- Crew Final Result ---")
    try:
        # Try to parse and pretty-print the JSON result
        parsed_result = json.loads(result)
        logger.info(json.dumps(parsed_result, indent=2))
    except (json.JSONDecodeError, TypeError):
        logger.warning("Final crew output was not valid JSON:")
        logger.warning(result)
    
    logger.info("✅ Crew run finished.")

if __name__ == "__main__":
    run_test()