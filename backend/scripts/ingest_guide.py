# FILE: backend/scripts/ingest_guide.py
import asyncio
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from pinecone import Pinecone

from src.core.config import settings
from src.models.knowledge_base import KnowledgeBaseGuide, KnowledgeBaseNode, KnowledgeBaseVectorMap, NodeType
from src.agents.rag_pipeline.embedding_models import PineconeEmbeddingModel

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

# --- Regex Patterns to Parse the Guide ---
# Matches major section headers like "2010AA Billing Provider Name Loop" or "CLM Claim Information"
MAJOR_HEADER_PATTERN = re.compile(r"^(?P<id>[A-Z0-9]{2,7})\s+(?P<name>.+?)(?:\s+Loop)?$")
# Matches element-level headers like "CLM-01", "ISA-11"
ELEMENT_HEADER_PATTERN = re.compile(r"^(?P<id>[A-Z0-9]+-[0-9]{2})\s+(?P<name>.*)$")

# --- Database and Pinecone Setup ---
engine = create_async_engine(settings.DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
PINECONE_INDEX_NAME = "edi-lens-knowledge-base"

# --- Main Ingestion Logic ---

class GuideIngestor:
    def __init__(self, guide_version: str, guide_name: str, guide_path: Path):
        self.guide_version = guide_version
        self.guide_name = guide_name
        self.guide_path = guide_path
        self.embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)
        self.db_session: Optional[AsyncSession] = None
        self.guide_db_obj: Optional[KnowledgeBaseGuide] = None

    async def run(self):
        """Orchestrates the entire ingestion process."""
        async with AsyncSessionLocal() as session:
            self.db_session = session
            await self._prepare_database_and_pinecone()
            
            raw_chunks = self._parse_guide_to_raw_chunks()
            db_nodes = await self._create_db_nodes(raw_chunks)
            
            await self._embed_and_upsert(db_nodes)
            
            logger.info("✅ Ingestion complete.")

    async def _prepare_database_and_pinecone(self):
        """Clears old data and prepares a new guide entry in the DB and Pinecone index."""
        logger.info(f"Preparing database and Pinecone for guide: {self.guide_version}")
        
        # 1. Clear existing guide data from PostgreSQL
        existing_guide = (await self.db_session.execute(
            select(KnowledgeBaseGuide).filter_by(version=self.guide_version)
        )).scalars().first()

        if existing_guide:
            logger.warning(f"Found existing guide '{self.guide_version}'. Deleting all associated data.")
            await self.db_session.delete(existing_guide)
            await self.db_session.commit()

        # 2. Create new guide entry
        self.guide_db_obj = KnowledgeBaseGuide(name=self.guide_name, version=self.guide_version)
        self.db_session.add(self.guide_db_obj)
        await self.db_session.commit()

        # 3. Prepare Pinecone index
        if PINECONE_INDEX_NAME in pc.list_indexes().names():
            logger.info(f"Pinecone index '{PINECONE_INDEX_NAME}' already exists. Clearing old vectors for this guide.")
            index = pc.Index(PINECONE_INDEX_NAME)
            # This deletes all vectors associated with the guide version
            index.delete(filter={"guide_version": self.guide_version})
        else:
            logger.info(f"Creating new Pinecone index '{PINECONE_INDEX_NAME}'.")
            # You might need to adjust the dimension based on your embedding model
            pc.create_index(name=PINECONE_INDEX_NAME, dimension=1024, metric="cosine")

    def _parse_guide_to_raw_chunks(self) -> List[Dict[str, Any]]:
        """Parses the flat text file into a list of structured chunks."""
        logger.info(f"Parsing guide file: {self.guide_path}")
        with open(self.guide_path, 'r', encoding='utf-8') as f:
            lines = [line for line in f if "Overview" not in line]

        chunks = []
        current_chunk = None

        for line in lines:
            major_match = MAJOR_HEADER_PATTERN.match(line.strip())
            element_match = ELEMENT_HEADER_PATTERN.match(line.strip())

            if major_match:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = {
                    "node_key": major_match.group('id'),
                    "name": major_match.group('name').strip(),
                    "node_type": NodeType.LOOP if "Loop" in line else NodeType.SEGMENT,
                    "text_lines": [line]
                }
            elif element_match and current_chunk:
                if current_chunk: # Save the previous chunk before starting a new one
                    chunks.append(current_chunk)
                current_chunk = {
                    "node_key": element_match.group('id'),
                    "name": element_match.group('name').strip(),
                    "node_type": NodeType.ELEMENT,
                    "text_lines": [line]
                }
            elif current_chunk:
                current_chunk["text_lines"].append(line)
        
        if current_chunk:
            chunks.append(current_chunk)

        # Post-process to join text lines
        for chunk in chunks:
            chunk['raw_text'] = "".join(chunk['text_lines']).strip()
            del chunk['text_lines']

        logger.info(f"Parsed {len(chunks)} raw chunks from guide.")
        return chunks

    async def _create_db_nodes(self, raw_chunks: List[Dict[str, Any]]) -> List[KnowledgeBaseNode]:
        """Creates and saves the hierarchical node structure in PostgreSQL."""
        logger.info("Creating node hierarchy in the database...")
        nodes_to_return = []
        parent_stack: List[KnowledgeBaseNode] = []
        node_map: Dict[str, KnowledgeBaseNode] = {}

        for chunk in raw_chunks:
            # Determine hierarchy
            parent_id = parent_stack[-1].id if parent_stack else None
            
            node = KnowledgeBaseNode(
                guide_id=self.guide_db_obj.id,
                parent_id=parent_id,
                node_type=chunk['node_type'],
                node_key=chunk['node_key'],
                name=chunk['name'],
                raw_text=chunk['raw_text']
            )
            self.db_session.add(node)
            nodes_to_return.append(node)
            node_map[chunk['node_key']] = node

            # This is a simplified hierarchy logic; a real implementation might need more sophisticated rules
            if chunk['node_type'] == NodeType.LOOP:
                parent_stack.append(node)
            elif chunk['node_type'] == NodeType.SEGMENT and parent_stack and parent_stack[-1].node_type == NodeType.LOOP:
                pass # Segment is a child of the current loop
            elif chunk['node_type'] == NodeType.ELEMENT and parent_stack and parent_stack[-1].node_type in [NodeType.SEGMENT, NodeType.LOOP]:
                 pass # Element is a child of the last segment/loop
            else:
                 # If we encounter a top-level segment, clear the parent stack
                 parent_stack = [node] if chunk['node_type'] in [NodeType.LOOP, NodeType.SEGMENT] else []
        
        await self.db_session.commit()
        logger.info(f"Saved {len(nodes_to_return)} nodes to the database.")
        return nodes_to_return

    async def _embed_and_upsert(self, db_nodes: List[KnowledgeBaseNode]):
        """Generates embeddings and upserts them to Pinecone, then links them in the DB."""
        logger.info(f"Generating embeddings for {len(db_nodes)} nodes...")
        
        index = pc.Index(PINECONE_INDEX_NAME)
        texts_to_embed = [node.raw_text for node in db_nodes]
        embeddings = self.embedding_model._get_text_embeddings(texts_to_embed)

        vectors_to_upsert = []
        vector_maps_to_create = []
        
        for node, embedding in zip(db_nodes, embeddings):
            vector_id = f"{self.guide_version}-{node.id}"
            vectors_to_upsert.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "guide_version": self.guide_version,
                    "node_id": node.id,
                    "node_key": node.node_key,
                    "node_type": node.node_type.value,
                    "text_preview": node.raw_text[:200]
                }
            })
            vector_maps_to_create.append(KnowledgeBaseVectorMap(
                node_id=node.id,
                pinecone_vector_id=vector_id
            ))

        logger.info(f"Upserting {len(vectors_to_upsert)} vectors to Pinecone...")
        # Upsert in batches for better performance
        batch_size = 100
        for i in range(0, len(vectors_to_upsert), batch_size):
            batch = vectors_to_upsert[i:i+batch_size]
            index.upsert(vectors=batch)

        logger.info("Linking nodes to vectors in the database...")
        self.db_session.add_all(vector_maps_to_create)
        await self.db_session.commit()


async def main():
    """Main function to run the ingestion process."""
    guide_file = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "x222a1.txt"
    if not guide_file.exists():
        logger.error(f"Guide file not found at: {guide_file}")
        return
        
    ingestor = GuideIngestor(
        guide_version="005010X222A1",
        guide_name="Health Care Claim: Professional (X222A1)",
        guide_path=guide_file
    )
    await ingestor.run()


if __name__ == "__main__":
    asyncio.run(main())