# FILE: backend/src/api/endpoints/enrichment.py
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()

# This file can be kept as a placeholder for any future, simple,
# non-streaming API endpoints related to enrichment or schema generation if needed.
# For now, it will be empty as the primary workflow is a command-line script.

@router.get("/enrichment/health", tags=["Enrichment"], include_in_schema=False)
def enrichment_health_check():
    return {"status": "ok"}