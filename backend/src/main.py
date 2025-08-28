# FILE: backend/src/main.py

import logging
log = logging.getLogger(__name__)
log.info("src.main module loaded")

from fastapi import FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
import os
import openlit

from src.api.endpoints import auth, schemas, edi, workflow_templates, workflows, workflow_execution
from src.core.auth import get_current_user, User
from src.core.config import setup_logging, settings
from src.core.audit import before_flush, after_flush_postexec
from src.core.schema_manager import schema_manager
# from src.core.metrics import PrometheusMiddleware, get_metrics_response, init_app_metrics

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan event started.")
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
    
    # Initialize metrics
    # init_app_metrics(version="1.0.0", environment=os.getenv("ENVIRONMENT", "development"))
    
    yield
    
    logger.info("--- Shutting down EDI Lens Validator API ---")


app = FastAPI(
    title="EDI Lens API",
    description="API for EDI processing, validation, and management.",
    version="1.0.0",
    lifespan=lifespan,
)

# Add Prometheus metrics middleware
# metrics_middleware = PrometheusMiddleware("edi-lens-backend")
# app.middleware("http")(metrics_middleware)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(edi.router, prefix="/api/v1")
app.include_router(schemas.router, prefix="/api/v1")
app.include_router(workflow_templates.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(workflow_execution.router, prefix="/api/v1")

@app.get("/api/v1/health", tags=["health"])
def health_check():
    return {"status": "ok"}

@app.get("/metrics", tags=["monitoring"])
def metrics():
    """Prometheus metrics endpoint"""
    return {"message": "Metrics endpoint placeholder - will be implemented with working monitoring system"}


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