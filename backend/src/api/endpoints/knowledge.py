# FILE: backend/src/api/endpoints/knowledge.py
import logging
import httpx
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse  # --- THIS IS THE FIX ---
from typing import List
from src.core.auth import require_permission

logger = logging.getLogger(__name__)
router = APIRouter()

LIGHTRAG_API_URL = "http://lightrag-server:9621"

@router.post(
    "/knowledge/ingest-guides",  # Renamed for clarity as it handles multiple files
    summary="Proxy for Implementation Guide Ingestion",
    description="Forwards one or more .txt guides to the LightRAG service for processing."
)
async def ingest_guides_endpoint(
    files: List[UploadFile] = File(...),
    auth: dict = Depends(require_permission("superuser"))
):
    # The OpenAPI spec shows the endpoint is /documents/upload and takes a single 'file'.
    # We will iterate through the uploaded files and send them individually.
    
    upload_results = []
    has_errors = False
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        for file in files:
            if not file.filename.endswith(".txt"):
                upload_results.append({"filename": file.filename, "status": "error", "detail": "Only .txt files are supported."})
                has_errors = True
                continue

            try:
                # Prepare the file for the multipart/form-data request with the correct field name 'file'
                file_content = await file.read()
                files_payload = {'file': (file.filename, file_content, file.content_type)}
                
                response = await client.post(f"{LIGHTRAG_API_URL}/documents/upload", files=files_payload)
                response.raise_for_status()
                
                upload_results.append({"filename": file.filename, "status": "success", "response": response.json()})

            except httpx.HTTPStatusError as e:
                has_errors = True
                upload_results.append({
                    "filename": file.filename,
                    "status": "error",
                    "detail": f"HTTP {e.response.status_code}: {e.response.text}"
                })
            except Exception as e:
                has_errors = True
                upload_results.append({"filename": file.filename, "status": "error", "detail": str(e)})

    # After all files are uploaded, trigger a single scan to process all of them.
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            scan_response = await client.post(f"{LIGHTRAG_API_URL}/documents/scan")
            scan_response.raise_for_status()
            scan_result = {"status": "success", "response": scan_response.json()}
    except httpx.HTTPStatusError as e:
        has_errors = True
        scan_result = {"status": "error", "detail": f"HTTP {e.response.status_code}: {e.response.text}"}


    final_status_code = status.HTTP_207_MULTI_STATUS if has_errors else status.HTTP_200_OK
    
    return JSONResponse(
        status_code=final_status_code,
        content={
            "message": "Ingestion process summary.",
            "uploads": upload_results,
            "scan_trigger": scan_result
        }
    )