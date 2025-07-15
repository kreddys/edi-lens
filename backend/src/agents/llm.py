# FILE: backend/src/agents/llm.py
import os
import logging
from crewai.llm import LLM as CrewLLM
import openlit
# --- THIS IS THE FIX: Import OpenTelemetry trace API ---
from opentelemetry import trace
from openlit.semcov import SemanticConvention
# --- END OF FIX ---

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("edi_lens_llm_tracer")

# --- THIS IS THE FIX: Define the custom callback function ---
def enrich_llm_span(kwargs, completion_response, start_time, end_time):
    """
    A LiteLLM callback to add detailed request/response data to the current OpenTelemetry span.
    """
    # Get the currently active span, which was created by OpenLIT's instrumentor
    current_span = trace.get_current_span()
    
    # If there is no active span, do nothing
    if not current_span.is_recording():
        return

    try:
        # Extract the prompt from the request messages
        messages = kwargs.get("messages", [])
        prompt_content = "\n---\n".join([f"{msg.get('role')}: {msg.get('content')}" for msg in messages])
        
        # Extract the completion from the response
        completion_content = ""
        if completion_response and completion_response.choices:
            completion_content = completion_response.choices[0].message.content or ""

        # Set the prompt and completion as attributes on the existing span
        current_span.set_attribute(SemanticConvention.GEN_AI_CONTENT_PROMPT, prompt_content)
        current_span.set_attribute(SemanticConvention.GEN_AI_CONTENT_COMPLETION, completion_content)
        
        # You can also add any other missing attributes here if needed
        # For example, let's ensure the model is always present
        current_span.set_attribute(SemanticConvention.GEN_AI_REQUEST_MODEL, kwargs.get("model", "unknown"))
        
        logger.debug("Successfully enriched LLM span with prompt and completion.")

    except Exception as e:
        logger.error(f"Error in enrich_llm_span callback: {e}", exc_info=True)
# --- END OF FIX ---


if os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true":
    logger.info("Observability is enabled. Initializing OpenLIT for agents...")
    openlit.init() 
else:
    logger.info("Observability is disabled for agents.")


def get_llm() -> CrewLLM:
    """
    Dynamically configures and returns a CrewAI LLM instance based on environment variables.
    """
    model_name = os.getenv("LLM_MODEL")
    if not model_name:
        logger.warning("LLM_MODEL environment variable not set. Defaulting to 'openrouter/deepseek/deepseek-chat'.")
        model_name = "openrouter/deepseek/deepseek-chat"

    logger.info(f"Configuring LLM for model: '{model_name}'")

    llm_config = {"model": model_name}

    if model_name.startswith("openrouter/"):
        llm_config["base_url"] = "https://openrouter.ai/api/v1"
        llm_config["api_key"] = os.getenv("OPENROUTER_API_KEY")
    elif model_name.startswith("ollama/"):
        llm_config["base_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # --- THIS IS THE FIX: Add the success callback to the LLM instance ---
    # This tells LiteLLM to run our 'enrich_llm_span' function after every successful API call.
    llm_instance = CrewLLM(**llm_config)
    llm_instance.success_callback = [enrich_llm_span]
    # --- END OF FIX ---

    logger.debug(f"Instantiating crewai.LLM with config: {llm_config}")
    
    return llm_instance