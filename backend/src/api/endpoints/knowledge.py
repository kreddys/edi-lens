# FILE: backend/src/api/endpoints/knowledge.py
import logging
import httpx
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from src.core.auth import require_permission

logger = logging.getLogger(__name__)
router = APIRouter()

LIGHTRAG_API_URL = "http://lightrag-server:9621"

@router.post(
    "/knowledge/ingest-guide",
    summary="Proxy for Implementation Guide Ingestion",
    description="Forwards a .txt guide to the LightRAG service for processing."
)
async def ingest_guide_endpoint(
    file: UploadFile = File(...),
    auth: dict = Depends(require_permission("superuser"))
):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported.")
    
    # We forward the file directly to the LightRAG server's batch upload endpoint
    files = {'files': (file.filename, await file.read(), file.content_type)}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LIGHTRAG_API_URL}/documents/batch",
                files=files,
                timeout=300.0 # Allow a long timeout for upload
            )
            response.raise_for_status()
            
            # After uploading, we trigger the scan to process it
            scan_response = await client.post(f"{LIGHTRAG_API_URL}/documents/scan", timeout=300.0)
            scan_response.raise_for_status()

            return {"message": "File uploaded and ingestion process started.", "ingestion_response": scan_response.json()}

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error forwarding to LightRAG service: {e.response.text}"
        )