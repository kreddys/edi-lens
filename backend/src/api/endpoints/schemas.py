import logging
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import PlainTextResponse, JSONResponse
from src.core.config import settings
from src.core.auth import require_permission

logger = logging.getLogger(__name__)
router = APIRouter()

# The schema directory is now read from the application settings.
SCHEMA_DIR = Path(settings.EDI_SCHEMA_DIRECTORY)

def get_safe_schema_path(schema_name: str) -> Path:
    """
    Validates the schema name and returns a safe Path object.
    Prevents directory traversal attacks.
    """
    if ".." in schema_name or "/" in schema_name or "\\" in schema_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid schema name."
        )
    
    path = (SCHEMA_DIR / schema_name).resolve()
    
    # Ensure the final path is still within the designated SCHEMA_DIR
    # This check is crucial for security
    if SCHEMA_DIR.resolve() not in path.parents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid schema path."
        )
        
    return path

@router.get(
    "/schemas",
    summary="List Available Schemas",
    description="Retrieves a list of all available schema filenames."
)
async def list_schemas(auth: dict = Depends(require_permission("superuser"))):
    if not SCHEMA_DIR.exists() or not SCHEMA_DIR.is_dir():
        logger.warning(f"Schema directory does not exist or is not a directory: {SCHEMA_DIR}")
        return []
    logger.info(f"Searching for schemas in: {SCHEMA_DIR}")
    files = [f.name for f in SCHEMA_DIR.glob("*.json")]
    logger.info(f"Found schema files: {files}")
    return files

@router.get(
    "/schemas/{schema_name}",
    response_class=JSONResponse,
    summary="Get Parsed Schema Content",
    description="Retrieves the parsed JSON content of a specific schema file."
)
async def get_schema_content(
    schema_name: str,
    auth: dict = Depends(require_permission("superuser"))
):
    schema_path = get_safe_schema_path(schema_name)
    if not schema_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found.")
    
    try:
        with open(schema_path, "r") as f:
            content = json.load(f)
        return JSONResponse(content=content)
    except Exception as e:
        logger.error(f"Error reading or parsing schema {schema_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not read or parse schema file: {e}")


@router.put(
    "/schemas/{schema_name}",
    status_code=status.HTTP_200_OK,
    summary="Update Schema File",
    description="Overwrites a schema file with new JSON content. Triggers a server reload in dev environments."
)
async def update_schema_content(
    schema_name: str,
    content: dict = Body(...), # Expect a parsed JSON object now
    auth: dict = Depends(require_permission("superuser"))
):
    schema_path = get_safe_schema_path(schema_name)
    
    try:
        # Write the new content to the file, pretty-printed with an indent of 2
        with open(schema_path, "w") as f:
            json.dump(content, f, indent=2)
        logger.info(f"User '{auth.username}' updated schema file: {schema_name}")
        return {"message": f"Schema '{schema_name}' updated successfully. Server may be reloading."}
    except Exception as e:
        logger.error(f"Failed to write schema file {schema_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write schema file: {e}"
        )