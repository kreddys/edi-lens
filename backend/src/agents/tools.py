# FILE: backend/src/agents/tools.py
import json
import logging
from typing import Any

from crewai.tools import tool
from src.core.schema_manager import schema_manager
from .utils import get_schema_toc, find_node_by_key

logger = logging.getLogger(__name__)

@tool("Schema Structure Reader")
def schema_structure_tool(schema_name: str) -> str:
    """
    Reads the high-level 'Table of Contents' of a specific EDI schema.
    Use this to find the unique keys of relevant loops and segments before
    retrieving their full definition.
    The `schema_name` must be a valid schema version like '005010X222A1'.
    """
    logger.info(f"Running SchemaStructureTool for schema '{schema_name}'.")
    schema_model = schema_manager.get_schema(schema_name)
    if not schema_model:
        msg = f"Schema '{schema_name}' not found in SchemaManager."
        logger.error(msg)
        return msg
        
    schema_data = json.loads(schema_model.model_dump_json())
    toc = get_schema_toc(json.dumps(schema_data))
    logger.debug(f"Generated TOC with {len(toc.splitlines())} lines for schema '{schema_name}'.")
    return toc

@tool("Node Definition Reader")
def node_definition_tool(schema_name: str, node_key: str) -> str:
    """
    Retrieves the full JSON definition for a specific node from a schema, given its unique key.
    The `schema_name` must be a valid schema version like '005010X222A1'.
    The `node_key` is the unique path to the node, e.g., 'loop:2000A.loop:2010AA'.
    """
    logger.info(f"Running NodeDefinitionTool for key: '{node_key}' in schema '{schema_name}'.")
    schema_model = schema_manager.get_schema(schema_name)
    if not schema_model:
        msg = f"Schema '{schema_name}' not found in SchemaManager."
        logger.error(msg)
        return msg

    schema_data = json.loads(schema_model.model_dump_json())
    node = find_node_by_key(schema_data, node_key)
    if not node:
        logger.warning(f"Node with key '{node_key}' not found in schema '{schema_name}'.")
        return f"Error: Node with key '{node_key}' not found."
    
    if node.get("type") == "segment":
        def_id = node.get("definitionId", node.get("xid"))
        node["definition"] = schema_data["segmentDefinitions"].get(def_id, {})
    
    result_json = json.dumps(node, indent=2)
    logger.debug(f"Found node for key '{node_key}'. Returning definition.")
    return result_json