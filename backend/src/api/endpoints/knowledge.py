# FILE: backend/src/api/endpoints/knowledge.py
import logging
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import StreamingResponse

from src.core.auth import require_permission
# --- FIX: Update the import path for the ingestor ---
from src.agents.ingestion.ingestor import GuideIngestor

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/knowledge/ingest-guide",
    summary="Ingest a New Implementation Guide",
    description=(
        "Upload a .txt implementation guide. The system will parse it, "
        "build a knowledge graph in the database, create vector embeddings, "
        "and store them for RAG. Requires 'superuser' permission."
    )
)
async def ingest_guide_endpoint(
    guide_version: str = Form(...),
    guide_name: str = Form(...),
    file: UploadFile = File(...),
    auth: dict = Depends(require_permission("superuser"))
):
    if not file.filename.endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload a .txt file."
        )
    
    guide_content = (await file.read()).decode("utf-8")

    async def stream_ingestion_progress():
        """Streams the progress of the ingestion back to the client."""
        ingestor = GuideIngestor(
            guide_version=guide_version,
            guide_name=guide_name,
            guide_content=guide_content
        )
        try:
            async for status_update in ingestor.run():
                yield f"data: {status_update}\n\n"
        except Exception as e:
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            yield f"error: Ingestion process failed with error: {e}\n\n"

    return StreamingResponse(stream_ingestion_progress(), media_type="text/event-stream")