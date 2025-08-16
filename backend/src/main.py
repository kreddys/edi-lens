# FILE: backend/src/main.py

from fastapi import FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import os
import openlit

from src.api.endpoints import auth, schemas, edi, workflow_templates
from src.core.auth import get_current_user, User
from src.core.config import setup_logging, settings
from src.core.audit import before_flush, after_flush_postexec
from src.core.schema_manager import schema_manager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("--- Starting up EDI Lens Validator API ---")
    
    if os.getenv("IS_PYTEST") != "true":
        if os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true":
            logger.info("Observability is enabled. Initializing OpenLIT for the application...")
            openlit.init()
        else:
            logger.info("Observability is disabled for the application.")
    else:
        logger.info("Skipping OpenLIT initialization in main.py (running in test mode).")
    
    schema_dir = Path(settings.EDI_SCHEMA_DIRECTORY)
    schema_manager.load_base_schemas(schema_dir)
    
    logger.info("Audit logging system initialized.")
    
    yield
    
    logger.info("--- Shutting down EDI Lens Validator API ---")


# --- THIS IS THE FIX: The app instantiation and CORS middleware were missing ---
from src.api.endpoints import (
    auth, edi, schemas, workflow_templates, workflows
)

app = FastAPI(
    title="EDI Lens API",
    description="API for EDI processing, validation, and management.",
    version="1.0.0",
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(edi.router, prefix="/api/v1")
app.include_router(schemas.router, prefix="/api/v1")
app.include_router(workflow_templates.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")

@app.get("/api/v1/health", tags=["health"])
def health_check():
    return {"status": "ok"}


origins = ["http://localhost:3000", "http://localhost:3001"]
if settings.REMOTE_HOST and settings.REMOTE_HOST != "localhost":
    prod_origin = f"https://{settings.REMOTE_HOST}"
    origins.append(prod_origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- END OF FIX ---


api_router = APIRouter(prefix="/api/v1")

@api_router.get("/health", tags=["Health"], summary="Health Check")
def health_check():
    logger.debug("Health check endpoint was called.")
    return {"status": "ok"}

@api_router.get("/users/me", response_model=User, tags=["Users"], summary="Get Current User")
async def read_users_me(current_user: User = Depends(get_current_user)):
    logger.info(f"User {current_user.username} fetched their profile.")
    return current_user

api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(edi.router, tags=["EDI Processing"])
api_router.include_router(schemas.router, tags=["Schema Management"])
api_router.include_router(workflow_templates.router, tags=["Workflow Templates"])

app.include_router(api_router)