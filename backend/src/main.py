# FILE: backend/src/main.py
from fastapi import FastAPI, Depends, APIRouter # <-- Add APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import os
import openlit

from src.api.endpoints import validation, trading_partners, auth, schemas, enrichment, knowledge
from src.core.auth import get_current_user, User
from src.core.config import setup_logging, settings
from src.core.audit import before_flush, after_flush_postexec
from src.core.schema_manager import schema_manager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... (this function remains unchanged) ...
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

app = FastAPI(
    title="EDI Lens Validator API",
    description="Backend API for the EDI Lens application, handling EDI validation, trading partner configuration, and user authentication.",
    version="1.0.0",
    lifespan=lifespan
)

# ... (origins and CORS middleware remain unchanged) ...
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

# --- THIS IS THE NEW, CONSOLIDATED ROUTER ---
api_router = APIRouter(prefix="/api/v1")

@api_router.get("/health", tags=["Health"], summary="Health Check")
def health_check():
    logger.debug("Health check endpoint was called.")
    return {"status": "ok"}

@api_router.get("/users/me", response_model=User, tags=["Users"], summary="Get Current User")
async def read_users_me(current_user: User = Depends(get_current_user)):
    logger.info(f"User {current_user.username} fetched their profile.")
    return current_user

# Attach all the existing endpoint routers to our new main api_router
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(validation.router, tags=["Validation"])
api_router.include_router(trading_partners.router, tags=["Trading Partners"])
api_router.include_router(schemas.router, tags=["Schemas"])
api_router.include_router(enrichment.router, tags=["Enrichment"])
api_router.include_router(knowledge.router, tags=["Knowledge Base"])

# Finally, include the main api_router in the app
app.include_router(api_router)
