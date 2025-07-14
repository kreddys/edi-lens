# FILE: backend/src/refinement_engine/rag_tool.py
import logging
from .models import KnowledgeSource
from crewai.tools import BaseTool
from pydantic import ConfigDict

logger = logging.getLogger(__name__)

class RAGTool(BaseTool):
    """
    A custom CrewAI tool for querying a knowledge source.
    This tool is stateful and is initialized with a specific document.
    """
    model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)
    
    name: str = "Documentation Query Tool"
    description: str = (
        "Queries the implementation guide documentation for specific rules or context. "
        "Use this to understand the requirements for a segment or loop. "
        "The input should be a clear, natural language question."
    )
    knowledge_source: KnowledgeSource

    # --- THIS IS THE FIX ---
    def __init__(self, knowledge_source: KnowledgeSource, **kwargs):
        # We must pass all arguments intended for the model's fields
        # to the parent's __init__ method for validation.
        super().__init__(knowledge_source=knowledge_source, **kwargs)
        
        # Now self.knowledge_source is already set by the super().__init__ call.
        # We can safely use it here.
        logger.info(f"RAGTool initialized with knowledge source: {self.knowledge_source.source_type}")
    # --- END OF FIX ---

    def _run(self, query: str) -> str:
        """
        Simulates querying the indexed knowledge base.
        """
        logger.debug(f"RAGTool received query: '{query}'")
        # This is a mock response. A real implementation would perform a
        # similarity search on the vector store and return relevant chunks.
        return (
            f"Based on the document provided ({self.knowledge_source.content}), "
            f"the answer to '{query}' involves updating the relevant entity "
            "to be compliant. For example, a 'usage' field might need to be "
            "changed from 'S' to 'R'."
        )