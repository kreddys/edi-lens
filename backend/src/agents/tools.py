import json
import logging
from typing import Type, Any
from pydantic import BaseModel, Field
from crewai_tools import BaseTool

from src.core.schema_manager import schema_manager
from .utils import get_schema_toc, find_node_by_key

# Get a logger for this module
logger = logging.getLogger(__name__)

class SchemaTool(BaseTool):
    """Base class for tools that need access to a specific EDI schema."""
    schema_name: str

    def __init__(self, schema_name: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.schema_name = schema_name
        logger.debug(f"Initializing SchemaTool for schema: '{self.schema_name}'")
        schema_model = schema_manager.get_schema(self.schema_name)
        if not schema_model:
            msg = f"Schema '{self.schema_name}' not found in SchemaManager."
            logger.error(msg)
            raise ValueError(msg)
        self._schema_data = json.loads(schema_model.model_dump_json())
        logger.info(f"Successfully loaded schema '{self.schema_name}' into tool.")

class SchemaStructureTool(SchemaTool):
    name: str = "Schema Structure Reader"
    description: str = "Reads the high-level 'Table of Contents' of the EDI schema. Use this to find the unique keys of relevant loops and segments before retrieving their full definition."

    def _run(self) -> str:
        """Returns a simplified text map of the entire schema structure."""
        logger.info(f"Running SchemaStructureTool for schema '{self.schema_name}'.")
        toc = get_schema_toc(json.dumps(self._schema_data))
        logger.debug(f"Generated TOC with {len(toc.splitlines())} lines.")
        return toc

class NodeDefinitionToolInput(BaseModel):
    """Input for NodeDefinitionTool."""
    node_key: str = Field(description="The unique key of the node to retrieve, e.g., 'loop:2000A.loop:2010AA'.")

class NodeDefinitionTool(SchemaTool):
    name: str = "Node Definition Reader"
    description: str = "Retrieves the full JSON definition for a specific node, given its unique key."
    args_schema: Type[BaseModel] = NodeDefinitionToolInput

    def _run(self, node_key: str) -> str:
        """Returns the full JSON definition of a single node."""
        logger.info(f"Running NodeDefinitionTool for key: '{node_key}' in schema '{self.schema_name}'.")
        node = find_node_by_key(self._schema_data, node_key)
        if not node:
            logger.warning(f"Node with key '{node_key}' not found in schema '{self.schema_name}'.")
            return f"Error: Node with key '{node_key}' not found."
        
        # Include segment definition if it's a segment node
        if node.get("type") == "segment":
            def_id = node.get("definitionId", node.get("xid"))
            node["definition"] = self._schema_data["segmentDefinitions"].get(def_id, {})
        
        result_json = json.dumps(node, indent=2)
        logger.debug(f"Found node for key '{node_key}'. Returning definition.")
        return result_json