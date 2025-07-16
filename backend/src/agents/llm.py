# FILE: backend/src/agents/llm.py
import os
import logging
from crewai.llm import LLM as CrewLLM
import openlit

logger = logging.getLogger(__name__)

if os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true":
    logger.info("Observability is enabled. Initializing OpenLIT for agents...")
    # OpenLIT will automatically instrument LiteLLM, no manual callbacks needed for this.
    openlit.init()
else:
    logger.info("Observability is disabled for agents.")

def get_llm() -> CrewLLM:
    """
    Dynamically configures and returns a CrewAI LLM instance based on environment variables.
    """
    model_name = os.getenv("LLM_MODEL")
    if not model_name:
        logger.warning("LLM_MODEL environment variable not set. Defaulting to 'anthropic/claude-3-sonnet-20240229'.")
        model_name = "anthropic/claude-3-sonnet-20240229"

    logger.info(f"Configuring LLM for model: '{model_name}'")

    llm_config = {"model": model_name}

    if model_name.startswith("openrouter/"):
        llm_config["base_url"] = "https://openrouter.ai/api/v1"
        llm_config["api_key"] = os.getenv("OPENROUTER_API_KEY")
    elif model_name.startswith("ollama/"):
        llm_config["base_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    # Add other provider configurations here if needed

    llm_instance = CrewLLM(**llm_config)
    
    logger.debug(f"Instantiating crewai.LLM with config: {llm_config}")
    
    return llm_instance