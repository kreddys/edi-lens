import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- Step 1: Set up project path and LOAD THE ENVIRONMENT ---
# This is now the first thing the script does.
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# The .env file is in the parent of the `backend` directory
env_path = project_root.parent / ".env.local" 
if env_path.exists():
    # This loads the variables from .env.local into os.environ
    load_dotenv(dotenv_path=env_path, override=True)
# --- End Setup ---


# --- Step 2: Now, import application modules ---
# These imports will now succeed because the environment is already populated.
from src.core.config import settings, setup_logging
from src.core.schema_manager import schema_manager
from src.agents.crew import create_schema_refinement_crew


# --- Step 3: Configure Logging ---
setup_logging()
logger = logging.getLogger(__name__)


def run_test():
    """Initializes and runs the schema refinement crew."""
    logger.info("--- Starting Schema Refinement Crew ---")

    # This check will now succeed because os.getenv can see the loaded variables.
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OLLAMA_BASE_URL"):
        logger.error("No LLM API key or configuration found.")
        logger.error("Please ensure the required API key for your chosen provider is set in your .env.local file.")
        return

    # Initialize the Schema Manager
    local_schema_path = str(project_root) + settings.EDI_SCHEMA_DIRECTORY.replace('/home/appuser/app', '')
    schema_dir = Path(local_schema_path)

    logger.info(f"Loading schemas from local path: {schema_dir}")
    schema_manager.load_schemas(schema_dir)
    logger.debug(f"Loaded schemas: {list(schema_manager._schemas.keys())}")

    # Define the user's request
    schema_to_edit = '005010X222A1'
    user_query = "In the 2010BA Subscriber Name loop, the NM1 segment's NM109 element (Subscriber Primary Identifier) should be required."
    
    logger.info("--- User Query ---")
    logger.info(user_query)
    logger.info("--------------------")

    # Create and run the crew
    crew = create_schema_refinement_crew(schema_name=schema_to_edit, user_input=user_query)
    
    logger.info("🚀 Kicking off the crew...")
    result = crew.kickoff()

    logger.info("--- Crew Final Result ---")
    try:
        parsed_result = json.loads(result)
        logger.info(json.dumps(parsed_result, indent=2))
    except (json.JSONDecodeError, TypeError):
        logger.warning("Final crew output was not valid JSON:")
        logger.warning(result)
    
    logger.info("✅ Crew run finished.")

if __name__ == "__main__":
    run_test()