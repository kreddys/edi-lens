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

    def _traverse_structure(self, nodes: List[StructureChild], segment_id: str, found_contexts: List[str], current_path: str = ""):
        """
        Recursively walks the schema structure to find all instances of a segment,
        using the hierarchical path to generate a unique context if one is not provided.
        """
        for node in nodes:
            # Build a unique path for the current node (e.g., "DETAIL/2000A/2010AA")
            new_path = f"{current_path}/{node.xid}" if current_path else node.xid

            if isinstance(node, StructureSegment) and node.xid == segment_id:
                # Prioritize the explicit contextId if it exists, otherwise fall back
                # to the guaranteed unique hierarchical path.
                context = node.contextId or new_path
                if context not in found_contexts:
                    found_contexts.append(context)
            elif isinstance(node, StructureLoop) and node.children:
                # Pass the new path down to the children for the next level of recursion.
                self._traverse_structure(node.children, segment_id, found_contexts, current_path=new_path)

    def _run(self, segment_id: str) -> str:
        """
        Counts the usage of a segment within the schema and returns the count and contexts.
        It intelligently uses the 'in-memory-generation' schema if available.
        """
        # This _run method does not need to be changed, as the fix is in the traversal logic.
        schema = schema_manager.get_schema_by_name("in-memory-generation.json")
        if not schema:
            schema = schema_manager.get_schema("005010X222A1")
        
        if not schema:
            return json.dumps({"error": "No EDI schema is currently loaded in the system."})

        found_contexts: List[str] = []
        # The initial call to the updated traversal function
        self._traverse_structure(schema.structure, segment_id, found_contexts)
        
        usage_count = len(found_contexts)
        
        response: Dict[str, Any] = {
            "segment_id": segment_id,
            "usage_count": usage_count,
            "contexts": found_contexts,
            "summary": f"The segment '{segment_id}' is used in {usage_count} distinct context(s) within the schema."
        }
        
        return json.dumps(response, indent=2)