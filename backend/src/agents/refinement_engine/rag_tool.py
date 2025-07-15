# FILE: backend/src/agents/refinement_engine/rag_tool.py
import logging
from pathlib import Path
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from llama_index.core import Document, VectorStoreIndex, ServiceContext 
from llama_index.core.node_parser import SentenceSplitter
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
    
    class RAGToolSchema(BaseModel):
        """Input for RAGTool."""
        query: str = Field(..., description="Mandatory query string")

    args_schema: type[BaseModel] = RAGToolSchema

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def __init__(self, knowledge_source: KnowledgeSource, embedding_model: BaseEmbedding, **kwargs):
        super().__init__(**kwargs)

        self.knowledge_source = knowledge_source
        self.embedding_model = embedding_model
        self.query_engine: Any = None
        
        logger.info(f"Initializing RAGTool with embedding model: {embedding_model.__class__.__name__}")
        
        loader = get_loader(self.knowledge_source)
        loaded_documents = loader.load()

        documents = [doc for doc in loaded_documents if doc.get_content().strip()]

        if documents:
            service_context = ServiceContext.from_defaults(
                llm=None, # We use the RAG tool for retrieval only, not synthesis
                embed_model=self.embedding_model,
                node_parser=SentenceSplitter(
                    paragraph_separator="\n---\n",
                    chunk_size=512,
                    chunk_overlap=20
                )
            )
            
            logger.info(f"Creating vector store index from {len(documents)} valid document(s)...")

            index = VectorStoreIndex.from_documents(
                documents, 
                service_context=service_context, 
                show_progress=True
            )
            
            self.query_engine = index.as_query_engine(
                service_context=service_context,
                # Retrieve the top 3 most relevant sections to give the agent more context
                similarity_top_k=3
            )

            logger.info("RAG query engine is ready.")
        else:
            logger.error("Document loader returned no valid documents with content. RAG engine will not be available.")
            self.query_engine = None

    def _run(self, query: str) -> str:
        """
        Queries the indexed knowledge base and returns the raw text of all
        retrieved source nodes, concatenated together. This provides a richer
        context to the agent than a simple synthesized answer.
        """
        logger.debug(f"RAGTool received query: '{query}'")
        if not self.query_engine:
            return "Error: RAG query engine is not initialized. Knowledge source may be missing or invalid."

        response = self.query_engine.query(query)

        if not response.source_nodes or response.source_nodes[0].score < 0.75:
            logger.warning(
                f"No relevant context found for query '{query}'. "
                f"Top score was: {response.source_nodes[0].score if response.source_nodes else 'N/A'}"
            )
            return "No relevant context found in the documentation for this query."
        
        # --- THIS IS THE FIX ---
        # Instead of returning str(response), which is a synthesized answer,
        # we return the combined raw text of all retrieved chunks.
        source_texts = [node.get_content() for node in response.source_nodes]
        return "\n\n---\n\n".join(source_texts)
        # --- END OF FIX ---