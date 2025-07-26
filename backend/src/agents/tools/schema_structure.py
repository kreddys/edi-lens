# FILE: backend/src/agents/tools/schema_structure.py
import json
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from typing import List, Dict, Any

from src.core.schema_manager import schema_manager
from src.edi_schemas.edi_guide import StructureChild, StructureLoop, StructureSegment

class SchemaStructureInput(BaseModel):
    """Input for the EDI_Schema_Structure_Tool."""
    segment_id: str = Field(..., description="The segment's base ID to search for, e.g., 'CLM'.")

class EDI_Schema_Structure_Tool(BaseTool):
    name: str = "EDI Schema Structure Tool"
    description: str = (
        "Analyzes the entire structure of the currently loaded schema to determine how many times a specific segment is used. "
        "Use this tool first to decide if a segment definition is 'shared' and requires specialization."
    )
    args_schema: type[BaseModel] = SchemaStructureInput

    def _traverse_structure(self, nodes: List[StructureChild], segment_id: str, found_contexts: List[str]):
        """Recursively walks the schema structure to find all instances of a segment."""
        for node in nodes:
            if isinstance(node, StructureSegment) and node.xid == segment_id:
                # Use contextId if available, otherwise construct a path for identification
                context = node.contextId or f"loop_{node.xid}"
                if context not in found_contexts:
                    found_contexts.append(context)
            elif isinstance(node, StructureLoop) and node.children:
                self._traverse_structure(node.children, segment_id, found_contexts)

    def _run(self, segment_id: str) -> str:
        """
        Counts the usage of a segment within the schema and returns the count and contexts.
        It intelligently uses the 'in-memory-generation' schema if available.
        """
        # Prioritize the in-memory schema used by the generation script
        schema = schema_manager.get_schema_by_name("in-memory-generation.json")
        if not schema:
            # Fallback for other potential uses (though not currently used)
            schema = schema_manager.get_schema("005010X222A1")
        
        if not schema:
            return json.dumps({"error": "No EDI schema is currently loaded in the system."})

        found_contexts: List[str] = []
        self._traverse_structure(schema.structure, segment_id, found_contexts)
        
        usage_count = len(found_contexts)
        
        response: Dict[str, Any] = {
            "segment_id": segment_id,
            "usage_count": usage_count,
            "contexts": found_contexts,
            "summary": f"The segment '{segment_id}' is used in {usage_count} distinct context(s) within the schema."
        }
        
        return json.dumps(response, indent=2)