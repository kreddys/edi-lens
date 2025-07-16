# FILE: backend/src/agents/refinement_engine/graph_rag_tool.py
import logging
import asyncio  # <<< THIS IS THE FIX
from typing import Any, List, Optional
from pydantic import BaseModel, Field

from crewai.tools import BaseTool
from pinecone import Pinecone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.models.knowledge_base import KnowledgeBaseNode

logger = logging.getLogger(__name__)

PINECONE_INDEX_NAME = "edi-lens-knowledge-base"

class GraphRAGToolInput(BaseModel):
    query: str = Field(..., description="A clear, natural language question or topic to find in the documentation.")
    node_key: Optional[str] = Field(None, description="An optional specific node key (e.g., 'CLM', '2010AA.NM1') to start the search from.")

class GraphRAGTool(BaseTool):
    name: str = "Hierarchical Documentation Query Tool"
    description: str = (
        "Queries the implementation guide, which is structured as a graph. "
        "Use this to retrieve context-aware information for a specific segment, element, or rule. "
        "Provide a natural language 'query' and optionally a 'node_key' to focus the search."
    )
    args_schema: type[BaseModel] = GraphRAGToolInput

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from .embedding_models import PineconeEmbeddingModel
        self.embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index = self.pc.Index(PINECONE_INDEX_NAME)
        logger.info("GraphRAGTool initialized.")

    async def _run_async(self, query: str, node_key: Optional[str] = None) -> str:
        """The async implementation of the tool's logic."""
        logger.info(f"Running GraphRAGTool with query='{query}' and node_key='{node_key}'")
        
        async with AsyncSessionLocal() as session:
            # Step 1: Semantic Search for initial nodes
            query_embedding = self.embedding_model._get_query_embedding(query)
            query_results = self.index.query(
                vector=query_embedding,
                top_k=3,
                include_metadata=True
            )
            
            initial_node_ids = [int(match['metadata']['node_id']) for match in query_results['matches']]
            if not initial_node_ids:
                return "No relevant information found for the query."

            # Step 2: Graph Traversal to expand context
            # Get the full node objects, their parents, and their children
            stmt = (
                select(KnowledgeBaseNode)
                .options(
                    selectinload(KnowledgeBaseNode.parent),
                    selectinload(KnowledgeBaseNode.children)
                )
                .where(KnowledgeBaseNode.id.in_(initial_node_ids))
            )
            
            result = await session.execute(stmt)
            retrieved_nodes = result.scalars().unique().all()

            # Step 3: Synthesize Context
            context_parts = []
            for node in retrieved_nodes:
                if node.parent:
                    context_parts.append(f"## Context from Parent: {node.parent.name} ({node.parent.node_key})\n{node.parent.raw_text}\n")
                
                context_parts.append(f"## Primary Information: {node.name} ({node.node_key})\n{node.raw_text}\n")

                if node.children:
                    context_parts.append("## Sub-topics / Children:\n")
                    for child in node.children[:3]: # Limit children to avoid excessive context
                        context_parts.append(f"- {child.name} ({child.node_key}): {child.raw_text[:150]}...")
            
            return "\n".join(context_parts)

    def _run(self, query: str, node_key: Optional[str] = None) -> str:
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self._run_async(query, node_key))