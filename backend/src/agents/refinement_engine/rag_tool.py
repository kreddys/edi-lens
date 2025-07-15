# FILE: backend/src/agents/refinement_engine/rag_tool.py
import logging
from typing import Any

from crewai.tools import BaseTool
# --- THIS IS THE FIX: Add the missing imports from pydantic ---
from pydantic import BaseModel, Field
# --- END OF FIX ---
from llama_index.core import VectorStoreIndex, ServiceContext, Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.base.embeddings.base import BaseEmbedding

from opentelemetry import trace
from openlit.semcov import SemanticConvention

from .document_loader import get_loader
from .models import KnowledgeSource

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("rag_tool_tracer")

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
                llm=None,
                embed_model=self.embedding_model,
                node_parser=SentenceSplitter(paragraph_separator="\n---\n", chunk_size=512, chunk_overlap=20)
            )
            logger.info(f"Creating vector store index from {len(documents)} valid document(s)...")
            index = VectorStoreIndex.from_documents(documents, service_context=service_context, show_progress=True)
            self.query_engine = index.as_query_engine(service_context=service_context, similarity_top_k=3)
            logger.info("RAG query engine is ready.")
        else:
            logger.error("Document loader returned no valid documents. RAG engine will not be available.")
            self.query_engine = None

    def _run(self, **kwargs: Any) -> str:
        """
        Queries the indexed knowledge base and returns the raw text of all
        retrieved source nodes. This method is now instrumented.
        """
        query = kwargs.get("query", "")
        with tracer.start_as_current_span(f"Tool Usage: {self.name}") as span:
            span.set_attribute(SemanticConvention.GEN_AI_TOOL_NAME, self.name)
            span.set_attribute(SemanticConvention.GEN_AI_TOOL_ARGS, query)

            logger.debug(f"RAGTool received query: '{query}'")
            if not self.query_engine:
                error_msg = "Error: RAG query engine is not initialized. Knowledge source may be missing or invalid."
                span.set_attribute("tool.output", error_msg)
                return error_msg

            response = self.query_engine.query(query)

            if not response.source_nodes or response.source_nodes[0].score < 0.75:
                logger.warning(f"No relevant context found for query '{query}'. Top score: {response.source_nodes[0].score if response.source_nodes else 'N/A'}")
                output = "No relevant context found in the documentation for this query."
            else:
                source_texts = [node.get_content() for node in response.source_nodes]
                output = "\n\n---\n\n".join(source_texts)

            span.set_attribute("tool.output", output)
            return output