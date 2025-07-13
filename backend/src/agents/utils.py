import json
from functools import lru_cache
from typing import Dict, List, Optional, Any

@lru_cache(maxsize=1)
def get_schema_toc(schema: str) -> str:
    """
    Creates a simplified, human-readable 'Table of Contents' for the schema structure.
    This is passed to the LLM to help it locate relevant nodes without seeing the full file.
    """
    schema_data = json.loads(schema)
    toc_lines = []

    def process_node(node: Dict[str, Any], prefix: str = "", level: int = 0):
        node_type = node.get("type")
        xid = node.get("xid")
        name = node.get("name")
        current_key = f"{prefix}.{node_type}:{xid}" if prefix else f"{node_type}:{xid}"
        
        indent = "  " * level
        toc_lines.append(f"{indent}- Key: `{current_key}` | Name: {name} ({xid})")
        
        if "children" in node and node["children"]:
            for child in node["children"]:
                process_node(child, current_key, level + 1)

    for root_node in schema_data.get("structure", []):
        process_node(root_node)
        
    return "\n".join(toc_lines)

def find_node_by_key(schema: Dict[str, Any], key_path: str) -> Optional[Dict[str, Any]]:
    """Finds a node in the schema structure using a dot-separated key path."""
    keys = key_path.split('.')
    current_nodes = schema.get("structure", [])
    
    for key in keys:
        found_node = None
        key_type, key_xid = key.split(':')
        
        for node in current_nodes:
            if node.get("type") == key_type and node.get("xid") == key_xid:
                found_node = node
                break
        
        if not found_node:
            return None
            
        current_nodes = found_node.get("children", [])
        
    return found_node