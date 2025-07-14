# FILE: backend/src/agents/refinement_engine/models.py
from pydantic import BaseModel, Field
from typing import Literal, Optional, Any, List, Dict

class KnowledgeSource(BaseModel):
    """
    Defines the source of knowledge for the refinement.
    Can be a file path or raw text content.
    """
    # --- THIS IS THE FIX ---
    # Added 'file_sections' to the list of allowed types.
    source_type: Literal["file", "text", "file_sections"]
    # --- END OF FIX ---
    content: str # For 'text', this is the raw text. For 'file', this is the path.

class RefinementTask(BaseModel):
    """Represents a single, discrete task for the worker crew."""
    task_type: str = Field(..., description="The type of operation, e.g., 'update_segment_definition'.")
    task_description: str = Field(..., description="A natural language description of what needs to be done.")
    entity_id: str = Field(..., description="The primary identifier for the task, e.g., a segment ID like 'CLM' or a loop ID.")

class RefinementStatus(BaseModel):
    """
    A structured status update yielded by the engine during its run.
    This is perfect for streaming to a UI.
    """
    phase: Literal["Planning", "Executing", "Complete", "Failed"]
    message: str
    progress: float = 0.0 # e.g., 0.0 to 1.0
    current_task_index: Optional[int] = None
    total_tasks: Optional[int] = None
    details: Optional[Dict[str, Any]] = None # For log data, patches, etc.