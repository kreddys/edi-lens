# FILE: backend/src/agents/tools/schema_lookup.py
import json
from typing import Dict, Any
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import copy
from pathlib import Path

from src.core.schema_manager import schema_manager
from src.core.config import settings # Import settings to get the directory

class SchemaLookupInput(BaseModel):
    """Input for the EDI_Schema_Lookup_Tool."""
    segment_id: str = Field(..., description="The segment's base ID to look up, e.g., 'NM1'.")
    context_id: str = Field(..., description="The specific contextual ID for the segment, e.g., '2010AA.NM1'.")

class EDI_Schema_Lookup_Tool(BaseTool):
    name: str = "EDI Schema Lookup Tool"
    description: str = (
        "Provides the current, authoritative definitions for an EDI segment from our internal schema. "
        "It returns the base definition, any contextual overrides, and the final 'effective' definition."
    )
    args_schema: type[BaseModel] = SchemaLookupInput

    def _ensure_schema_loaded(self):
        """A robust method to ensure the schema is loaded before use."""
        # Check if the desired schema is already loaded
        if schema_manager.get_schema("005010X222A1"):
            return
        
        # If not, load it directly.
        # This makes the tool resilient to different execution contexts.
        schema_dir = Path(settings.EDI_SCHEMA_DIRECTORY)
        schema_manager.load_schemas(schema_dir)

    def _run(self, segment_id: str, context_id: str) -> str:
        """
        Looks up a segment's base and contextual definitions and synthesizes the effective definition.
        """
        self._ensure_schema_loaded()
        
        schema = schema_manager.get_schema("005010X222A1")
        if not schema:
            # This error should now be virtually impossible to hit
            return json.dumps({"error": "The base 837P X222A1 schema is not loaded, and could not be loaded on demand."})

        response: Dict[str, Any] = {
            "contextId": context_id,
            "baseDefinition": None,
            "contextualDefinition": None,
            "effectiveDefinition": None,
            "error": None
        }

        # The schema uses Pydantic models, so we access them as attributes
        base_def_model = schema.segmentDefinitions.get(segment_id)
        if not base_def_model:
            response["error"] = f"Base definition for segment '{segment_id}' not found."
            return json.dumps(response, indent=2)
        
        base_def_dict = base_def_model.model_dump(exclude_none=True)
        response["baseDefinition"] = base_def_dict
        
        effective_def = copy.deepcopy(base_def_dict)

        context_def_model = schema.contextualDefinitions.get(context_id)
        if context_def_model:
            context_def_dict = context_def_model.model_dump(exclude_none=True)
            response["contextualDefinition"] = context_def_dict
            
            for el_xid, overrides in context_def_dict.get("elements", {}).items():
                for i, base_el in enumerate(effective_def.get("elements", [])):
                    if base_el.get("xid") == el_xid:
                        # Merge override properties into the element
                        for key, value in overrides.items():
                            if value is not None:
                                effective_def["elements"][i][key] = value
                        break
        
        response["effectiveDefinition"] = effective_def
        return json.dumps(response, indent=2)