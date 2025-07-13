import os
import logging
from crewai.llm import LLM as CrewLLM

logger = logging.getLogger(__name__)

def get_llm() -> CrewLLM:
    """
    Dynamically configures and returns a CrewAI LLM instance based on environment variables.
    This approach is provider-agnostic and relies on CrewAI's native LiteLLM integration.
    """
    model_name = os.getenv("LLM_MODEL")
    if not model_name:
        logger.warning("LLM_MODEL environment variable not set. Defaulting to 'openrouter/deepseek/deepseek-chat'.")
        model_name = "openrouter/deepseek/deepseek-chat"

    logger.info(f"Configuring LLM for model: '{model_name}'")

    # The configuration dictionary that will be passed to the LLM constructor.
    llm_config = {
        "model": model_name,
        # Add any other universal parameters like temperature here if needed
    }

    # Dynamically add provider-specific configurations
    # This is the correct way to handle providers that need more than just an API key.
    if model_name.startswith("openrouter/"):
        llm_config["base_url"] = "https://openrouter.ai/api/v1"
        llm_config["api_key"] = os.getenv("OPENROUTER_API_KEY")

    elif model_name.startswith("ollama/"):
        llm_config["base_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # For providers like 'openai/' or 'anthropic/', LiteLLM will automatically
    # use the OPENAI_API_KEY and ANTHROPIC_API_KEY from the environment,
    # so no extra configuration is needed in this factory.

    logger.debug(f"Instantiating crewai.LLM with config: {llm_config}")

    # Use dictionary unpacking to pass the dynamic configuration to the LLM class.
    return CrewLLM(**llm_config)