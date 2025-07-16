# FILE: backend/src/agents/ingestion/ingestor.py
import asyncio
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pinecone import Pinecone

from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.models.knowledge_base import KnowledgeBaseGuide, KnowledgeBaseNode, KnowledgeBaseVectorMap, NodeType
from src.agents.rag_pipeline.embedding_models import PineconeEmbeddingModel

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

# --- Regex Patterns to Parse the Guide ---
MAJOR_HEADER_PATTERN = re.compile(r"^(?P<id>[A-Z0-9]{2,7})\s+(?P<name>.+?)(?:\s+Loop)?$")
ELEMENT_HEADER_PATTERN = re.compile(r"^(?P<id>[A-Z0-9]+-[0-9]{2})\s+(?P<name>.*)$")

PINECONE_INDEX_NAME = "edi-lens-knowledge-base"

class GuideIngestor:
    """
    A service class responsible for parsing an implementation guide, structuring it
    into a knowledge graph in PostgreSQL, and creating vector embeddings in Pinecone.
    """
    def __init__(self, guide_version: str, guide_name: str, guide_content: str):
        self.guide_version = guide_version
        self.guide_name = guide_name
        self.guide_lines = guide_content.splitlines()
        self.embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)
        self.db_session: Optional[AsyncSession] = None
        self.guide_db_obj: Optional[KnowledgeBaseGuide] = None
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)

    async def run(self) -> AsyncGenerator[str, None]:
        """
        Orchestrates the entire ingestion process, yielding status updates.
        """
        async with AsyncSessionLocal() as session:
            self.db_session = session
            
            yield "Preparing database and vector store..."
            await self._prepare_database_and_pinecone()
            
            yield "Parsing guide file into structured chunks..."
            raw_chunks = self._parse_guide_to_raw_chunks()
            
            yield f"Creating {len(raw_chunks)} nodes in the database..."
            db_nodes = await self._create_db_nodes(raw_chunks)
            
            yield f"Generating embeddings and upserting {len(db_nodes)} vectors to Pinecone..."
            await self._embed_and_upsert(db_nodes)
            
            yield "Ingestion complete."

    async def _prepare_database_and_pinecone(self):
        """Clears old data and prepares a new guide entry in the DB and Pinecone index."""
        logger.info(f"Preparing database and Pinecone for guide: {self.guide_version}")
        
        existing_guide = (await self.db_session.execute(
            select(KnowledgeBaseGuide).filter_by(version=self.guide_version)
        )).scalars().first()

        if existing_guide:
            logger.warning(f"Found existing guide '{self.guide_version}'. Deleting all associated data.")
            await self.db_session.delete(existing_guide)
            await self.db_session.commit()

        self.guide_db_obj = KnowledgeBaseGuide(name=self.guide_name, version=self.guide_version)
        self.db_session.add(self.guide_db_obj)
        await self.db_session.commit()

        if PINECONE_INDEX_NAME in self.pc.list_indexes().names():
            logger.info(f"Clearing old vectors for guide '{self.guide_version}' from Pinecone index.")
            index = self.pc.Index(PINECONE_INDEX_NAME)
            index.delete(filter={"guide_version": self.guide_version})
        else:
            logger.info(f"Creating new Pinecone index '{PINECONE_INDEX_NAME}'.")
            self.pc.create_index(name=PINECONE_INDEX_NAME, dimension=1024, metric="cosine")

    def _parse_guide_to_raw_chunks(self) -> List[Dict[str, Any]]:
        """Parses the flat text file into a list of structured chunks."""
        lines = [line for line in self.guide_lines if "Overview" not in line]
        chunks = []
        current_chunk = None

        for line in lines:
            major_match = MAJOR_HEADER_PATTERN.match(line.strip())
            element_match = ELEMENT_HEADER_PATTERN.match(line.strip())

            if major_match:
                if current_chunk: chunks.append(current_chunk)
                current_chunk = {
                    "node_key": major_match.group('id'), "name": major_match.group('name').strip(),
                    "node_type": NodeType.LOOP if "Loop" in line else NodeType.SEGMENT, "text_lines": [line]
                }
            elif element_match and current_chunk:
                if current_chunk: chunks.append(current_chunk)
                current_chunk = {
                    "node_key": element_match.group('id'), "name": element_match.group('name').strip(),
                    "node_type": NodeType.ELEMENT, "text_lines": [line]
                }
            elif current_chunk:
                current_chunk["text_lines"].append(line)
        
        if current_chunk: chunks.append(current_chunk)

        for chunk in chunks:
            chunk['raw_text'] = "".join(chunk['text_lines']).strip()
            del chunk['text_lines']

        logger.info(f"Parsed {len(chunks)} raw chunks from guide.")
        return chunks

    async def _create_db_nodes(self, raw_chunks: List[Dict[str, Any]]) -> List[KnowledgeBaseNode]:
        """Creates and saves the hierarchical node structure in PostgreSQL."""
        nodes_to_return = []
        parent_stack: List[KnowledgeBaseNode] = []
        
        for chunk in raw_chunks:
            parent_id = parent_stack[-1].id if parent_stack else None
            node = KnowledgeBaseNode(
                guide_id=self.guide_db_obj.id, parent_id=parent_id,
                node_type=chunk['node_type'], node_key=chunk['node_key'],
                name=chunk['name'], raw_text=chunk['raw_text']
            )
            self.db_session.add(node)
            nodes_to_return.append(node)

            if chunk['node_type'] == NodeType.LOOP:
                parent_stack.append(node)
            elif chunk['node_type'] == NodeType.SEGMENT and parent_stack and parent_stack[-1].node_type == NodeType.LOOP:
                pass
            else:
                parent_stack = [node] if chunk['node_type'] in [NodeType.LOOP, NodeType.SEGMENT] else []
        
        await self.db_session.commit()
        return nodes_to_return

    async def _embed_and_upsert(self, db_nodes: List[KnowledgeBaseNode]):
        """Generates embeddings and upserts them to Pinecone, then links them in the DB."""
        index = self.pc.Index(PINECONE_INDEX_NAME)
        texts_to_embed = [node.raw_text for node in db_nodes]
        embeddings = self.embedding_model._get_text_embeddings(texts_to_embed)

        vectors_to_upsert = []
        vector_maps_to_create = []
        
        for node, embedding in zip(db_nodes, embeddings):
            vector_id = f"{self.guide_version}-{node.id}"
            vectors_to_upsert.append({
                "id": vector_id, "values": embedding,
                "metadata": {
                    "guide_version": self.guide_version, "node_id": node.id, "node_key": node.node_key,
                    "node_type": node.node_type.value, "text_preview": node.raw_text[:200]
                }
            })
            vector_maps_to_create.append(KnowledgeBaseVectorMap(node_id=node.id, pinecone_vector_id=vector_id))

        batch_size = 100
        for i in range(0, len(vectors_to_upsert), batch_size):
            index.upsert(vectors=vectors_to_upsert[i:i+batch_size])

        self.db_session.add_all(vector_maps_to_create)
        await self.db_session.commit()