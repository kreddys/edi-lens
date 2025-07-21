# FILE: backend/src/api/endpoints/knowledge.py
import logging
import httpx
import os
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List
from src.core.auth import require_permission, AuthContext

logger = logging.getLogger(__name__)
router = APIRouter()

# Use an environment variable for the LightRAG URL
LIGHTRAG_API_URL = os.getenv("LIGHTRAG_API_URL", "http://lightrag-server:9621")

@router.get(
    "/knowledge/sources",
    summary="List Ingested Knowledge Sources",
    description="Retrieves a list of all documents currently in the LightRAG knowledge base."
)
async def list_sources(auth: AuthContext = Depends(require_permission("superuser"))):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{LIGHTRAG_API_URL}/documents")
            response.raise_for_status()
            # The response is complex, let's simplify it for the UI
            # We'll flatten the statuses into a single list
            all_docs = []
            source_data = response.json()
            for status_group in source_data.get("statuses", {}).values():
                for doc in status_group:
                    all_docs.append({
                        "id": doc.get("id"),
                        "fileName": doc.get("file_path", "N/A").split("/")[-1],
                        "status": doc.get("status"),
                        "createdAt": doc.get("created_at"),
                    })
            return all_docs
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"LightRAG Error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.delete(
    "/knowledge/sources/{doc_id}",
    summary="Delete a Knowledge Source",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Deletes a document and all its associated data from the LightRAG knowledge base."
)
async def delete_source(doc_id: str, auth: AuthContext = Depends(require_permission("superuser"))):
    delete_payload = {"doc_ids": [doc_id], "delete_file": True}
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # First, delete the document
            delete_response = await client.request("DELETE", f"{LIGHTRAG_API_URL}/documents/delete_document", json=delete_payload)
            delete_response.raise_for_status()
            # Second, clear the query cache to ensure freshness
            await client.post(f"{LIGHTRAG_API_URL}/documents/clear_cache", json={})
            return
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"LightRAG Error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/knowledge/ingest-guides",
    summary="Proxy for Implementation Guide Ingestion",
    description="Forwards one or more .txt guides to the LightRAG service for processing."
)
async def ingest_guides_endpoint(
    files: List[UploadFile] = File(...),
    auth: AuthContext = Depends(require_permission("superuser"))
):
    upload_results = []
    has_errors = False
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        for file in files:
            if not file.filename or not file.filename.endswith(".txt"):
                upload_results.append({"filename": file.filename, "status": "error", "detail": "Only .txt files are supported."})
                has_errors = True
                continue

            try:
                file_content = await file.read()
                files_payload = {'file': (file.filename, file_content, file.content_type)}
                
                response = await client.post(f"{LIGHTRAG_API_URL}/documents/upload", files=files_payload)
                response.raise_for_status()
                
                upload_results.append({"filename": file.filename, "status": "success", "response": response.json()})

            except httpx.HTTPStatusError as e:
                has_errors = True
                upload_results.append({ "filename": file.filename, "status": "error", "detail": f"HTTP {e.response.status_code}: {e.response.text}"})
            except Exception as e:
                has_errors = True
                upload_results.append({"filename": file.filename, "status": "error", "detail": str(e)})

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            scan_response = await client.post(f"{LIGHTRAG_API_URL}/documents/scan")
            scan_response.raise_for_status()
            scan_result = {"status": "success", "response": scan_response.json()}
    except httpx.HTTPStatusError as e:
        has_errors = True
        scan_result = {"status": "error", "detail": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        has_errors = True
        scan_result = {"status": "error", "detail": str(e)}

    final_status_code = status.HTTP_207_MULTI_STATUS if has_errors else status.HTTP_200_OK
    
    return JSONResponse(
        status_code=final_status_code,
        content={
            "message": "Ingestion process summary.",
            "uploads": upload_results,
            "scan_trigger": scan_result
        }
    )