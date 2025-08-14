import logging
import json
from fastapi import APIRouter, Depends, HTTPException, status, Body
from src.core.config import settings
from src.core.auth import require_permission, AuthContext
from src.core.schema_manager import schema_manager
from src.core.storage import storage_client

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get(
    "/schemas",
    summary="List All Available Schemas for Tenant",
    description="Retrieves a list of base schemas and any specialized schemas for the current tenant."
)
async def list_schemas(auth: AuthContext = Depends(require_permission("schemas:read"))):
    base_schemas = schema_manager.list_base_schemas()
    
    tenant_prefix = f"{auth.tenant_id}/schemas/"
    tenant_schema_keys = storage_client.list_objects(prefix=tenant_prefix)
    # Extract just the filename from the full S3 key
    tenant_schema_names = [key.split('/')[-1] for key in tenant_schema_keys]

    return {
        "base_schemas": sorted(base_schemas),
        "specialized_schemas": sorted(tenant_schema_names)
    }

@router.get(
    "/schemas/{schema_name}",
    summary="Get Schema Content",
    description="Retrieves the JSON content of a specific schema, checking both base and tenant-specific schemas."
)
async def get_schema_content(
    schema_name: str,
    auth: AuthContext = Depends(require_permission("schemas:read"))
):
    schema = schema_manager.get_schema(schema_name, auth.tenant_id)
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found.")
    
    # We return the model dict, which FastAPI will serialize to JSON
    return schema.model_dump(by_alias=True)

@router.put(
    "/schemas/{schema_name}",
    summary="Update a Specialized Schema",
    description="Overwrites a specialized schema file for the current tenant with new JSON content."
)
async def update_schema_content(
    schema_name: str,
    content: dict = Body(...),
    auth: AuthContext = Depends(require_permission("schemas:update")) # Requires update perm
):
    if schema_name in schema_manager.list_base_schemas():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Base schemas cannot be modified."
        )

    try:
        # Pydantic validation before saving
        from src.edi_schemas.edi_guide import ImplementationGuideSchema
        ImplementationGuideSchema.model_validate(content)
        
        schema_bytes = json.dumps(content, indent=2).encode('utf-8')
        s3_key = f"{auth.tenant_id}/schemas/{schema_name}"
        storage_client.upload(data=schema_bytes, key=s3_key)
        
        # Invalidate the cache for this schema
        cache_key = f"{auth.tenant_id}/{schema_name}"
        if cache_key in schema_manager._specialized_schemas_cache:
            del schema_manager._specialized_schemas_cache[cache_key]

        return {"message": f"Specialized schema '{schema_name}' updated successfully."}
    except Exception as e:
        logger.error(f"Failed to write schema file {schema_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write schema file: {e}"
        )

@router.post(
    "/schemas/{base_schema_name}/copy",
    summary="Create a Specialized Schema from a Base",
    status_code=status.HTTP_201_CREATED,
)
async def copy_schema(
    base_schema_name: str,
    request: dict = Body(...), # Expects {"new_name": "..."}
    auth: AuthContext = Depends(require_permission("schemas:create"))
):
    new_name = request.get("new_name")
    if not new_name:
        raise HTTPException(status_code=400, detail="`new_name` is required.")
    
    # 1. Load the base schema content
    base_schema = schema_manager.get_schema(base_schema_name, tenant_id="base") # Use a dummy tenant for base
    if not base_schema:
        raise HTTPException(status_code=404, detail=f"Base schema '{base_schema_name}' not found.")

    # 2. Check for name collision in tenant's storage
    s3_key = f"{auth.tenant_id}/schemas/{new_name}"
    if storage_client.download(s3_key) is not None:
        raise HTTPException(status_code=409, detail=f"A schema named '{new_name}' already exists for this tenant.")

    # 3. Upload the new copy
    try:
        schema_bytes = json.dumps(base_schema.model_dump(by_alias=True), indent=2).encode('utf-8')
        storage_client.upload(data=schema_bytes, key=s3_key)
        return {"message": "Schema specialized successfully", "new_schema_name": new_name}
    except Exception as e:
        logger.error(f"Failed to copy schema: {e}")
        raise HTTPException(status_code=500, detail="Could not create specialized schema.")