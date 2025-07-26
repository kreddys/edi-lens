# FILE: backend/src/agents/tools/schema_lookup.py
import json
from typing import Dict, Any
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import copy
from pathlib import Path

from src.core.schema_manager import schema_manager
from src.core.config import settings

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

    def _run(self, segment_id: str, context_id: str) -> str:
        """
        Looks up a segment's definitions and synthesizes the effective definition.
        It intelligently uses the 'in-memory-generation' schema if available.
        """
        # Prioritize the in-memory schema used by the generation script
        schema = schema_manager.get_schema_by_name("in-memory-generation.json")
        if not schema:
            # Fallback for other potential uses
            schema = schema_manager.get_schema("005010X222A1")

        if not schema:
            return json.dumps({"error": "No EDI schema is currently loaded in the system."})

        response: Dict[str, Any] = {
            "contextId": context_id, "baseDefinition": None,
            "contextualDefinition": None, "effectiveDefinition": None, "error": None
        }

        base_def_model = schema.segmentDefinitions.get(segment_id)
        if not base_def_model:
            response["summary"] = f"Lookup successful: No base definition for segment '{segment_id}' found in the current schema state."
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
                        for key, value in overrides.items():
                            if value is not None:
                                effective_def["elements"][i][key] = value
                        break
        
        response["effectiveDefinition"] = effective_def
        return json.dumps(response, indent=2)