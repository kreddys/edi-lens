# FILE: backend/src/agents/prompt_utils.py
import json
from src.agents.models import UniversalAgentResponse

def get_pydantic_model_schemas() -> str:
    """
    Generates a JSON string containing the JSON Schemas for the core
    Pydantic models used in agent responses.
    """
    # Pydantic's `model_json_schema()` generates a dictionary
    schema_dict = UniversalAgentResponse.model_json_schema()
    
    # We can make it a bit more readable for the LLM
    # by removing some verbose keys it doesn't need.
    if "$defs" in schema_dict:
        if "ElementEnrichment" in schema_dict["$defs"]:
            schema_dict["$defs"]["ElementEnrichment"].pop("model_config", None)
        if "UniversalAgentResponse" in schema_dict["$defs"]:
            schema_dict["$defs"]["UniversalAgentResponse"].pop("model_config", None)
            
    return json.dumps(schema_dict, indent=2)