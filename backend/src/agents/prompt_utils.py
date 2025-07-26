# FILE: backend/src/agents/prompt_utils.py
import json

# --- THIS IS THE FIX (Part 1): Import the correct utilities ---
from pydantic.json_schema import models_json_schema

# Import the specific Pydantic models we need from the main schema definitions
from src.edi_schemas.edi_guide import SegmentDefinition

# Import the models that define the agent's final output structure
from src.agents.models import UniversalAgentResponse

def get_pydantic_model_schemas() -> str:
    """
    DEPRECATED: Generates the full, verbose schema.
    Kept for compatibility in case other agents use it.
    """
    schema_dict = UniversalAgentResponse.model_json_schema()
    # Clean up verbose keys
    if "$defs" in schema_dict:
        if "ElementEnrichment" in schema_dict["$defs"]:
            schema_dict["$defs"]["ElementEnrichment"].pop("model_config", None)
        if "UniversalAgentResponse" in schema_dict["$defs"]:
            schema_dict["$defs"]["UniversalAgentResponse"].pop("model_config", None)
    return json.dumps(schema_dict, indent=2)

def get_focused_schema_for_enrichment() -> str:
    """
    Generates a focused and cleaner JSON schema string containing only the definitions
    necessary for the element enrichment task. This significantly reduces token count.
    """
    # --- THIS IS THE FIX (Part 2): Use the correct function `models_json_schema` ---
    # This function is designed to take a list of Pydantic models and generate a single,
    # unified schema with a '$defs' section.
    _, schema_results = models_json_schema(
        [
            (UniversalAgentResponse, 'validation'),
            (SegmentDefinition, 'validation')
        ],
        ref_template="#/$defs/{model}"
    )
    # --- END OF FIX ---

    # Clean up the generated schema to remove unnecessary verbosity for the LLM
    if "$defs" in schema_results:
        for model_def in schema_results["$defs"].values():
            model_def.pop("model_config", None)
            if "properties" in model_def:
                for prop_def in model_def["properties"].values():
                    # Removing 'title' makes the schema much more compact
                    prop_def.pop("title", None)

    return json.dumps(schema_results, indent=2)