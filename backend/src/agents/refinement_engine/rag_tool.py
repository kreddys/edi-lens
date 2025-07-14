# FILE: backend/src/agents/refinement_engine/rag_tool.py
import logging
from pathlib import Path
from typing import Any

from crewai.tools import BaseTool
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding

from .document_loader import get_loader
from .models import KnowledgeSource

logger = logging.getLogger(__name__)


class RAGTool(BaseTool):
    """
    A custom CrewAI tool for querying a knowledge source using a real RAG pipeline.
    """
    name: str = "Documentation Query Tool"
    description: str = (
        "Queries the implementation guide documentation for specific rules or context. "
        "Use this to understand the requirements for a segment or loop. "
        "The input should be a clear, natural language question."
    )
    
    # --- THIS IS THE FIX ---
    # We remove the field declarations from the class body.
    # We will set them manually in __init__ after the parent is initialized.
    class Config:
        # This is the key: it allows us to set arbitrary attributes on the instance.
        arbitrary_types_allowed = True
        extra = "allow"
    # --- END OF FIX ---

    def __init__(self, knowledge_source: KnowledgeSource, embedding_model: BaseEmbedding, **kwargs):
        # Call the parent __init__ with only the arguments it knows about.
        super().__init__(**kwargs)

        # Now, manually set our custom attributes on the instance.
        self.knowledge_source = knowledge_source
        self.embedding_model = embedding_model
        self.query_engine: Any = None
        
        logger.info(f"Initializing RAGTool with embedding model: {self.embedding_model.__class__.__name__}")
        
        Settings.embed_model = self.embedding_model
        Settings.llm = None

        loader = get_loader(self.knowledge_source)
        documents = loader.load()

        if documents:
            logger.info("Creating vector store index from document(s)...")
            index = VectorStoreIndex.from_documents(documents, show_progress=True)
            self.query_engine = index.as_query_engine()
            logger.info("RAG query engine is ready.")
        else:
            logger.error("Document loader returned no documents. RAG engine will not be available.")


    def _run(self, query: str) -> str:
        """
        Queries the indexed knowledge base.
        """
        logger.debug(f"RAGTool received query: '{query}'")
        if not self.query_engine:
            return "Error: RAG query engine is not initialized. Knowledge source may be missing or invalid."

        response = self.query_engine.query(query)
        return str(response)