"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import time

from .api.routes.health import router as health_router
from .api.routes.flows import router as flows_router
from .api.routes.templates import router as templates_router
from .core.config import settings
from .core.database import dispose_engine
from .core.logging import setup_logging, get_logger, audit_logger

# Initialize logging system
setup_logging(settings)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting EDI Lens NiFi Backend v%s", settings.APP_VERSION)
    logger.info("Configuration: Debug=%s, NiFi=%s, Registry=%s",
                settings.DEBUG, settings.nifi_url, settings.registry_url)
    audit_logger.log_system_event("application_startup", {
        "version": settings.APP_VERSION,
        "debug": settings.DEBUG,
        "nifi_url": settings.nifi_url,
        "registry_url": settings.registry_url
    })
    
    yield
    
    # Shutdown
    logger.info("Shutting down EDI Lens NiFi Backend")
    audit_logger.log_system_event("application_shutdown")
    await dispose_engine()


app = FastAPI(
    title="EDI Lens NiFi Backend",
    description="Deployment-first NiFi flow management backend",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests for monitoring and debugging."""
    start_time = time.time()
    
    # Log request
    logger.debug("Incoming request: %s %s", request.method, request.url.path)
    logger.debug("Request headers: %s", dict(request.headers))
    
    # Process request
    response: Response = await call_next(request)
    
    # Calculate execution time
    execution_time = (time.time() - start_time) * 1000
    
    # Log response
    logger.info("%s %s -> %d (%.2fms)", 
                request.method, request.url.path, response.status_code, execution_time)
    
    # Audit log for API calls
    if request.url.path.startswith("/api/"):
        audit_logger.log_api_call(
            method=request.method,
            endpoint=request.url.path,
            response_status=response.status_code,
            execution_time_ms=execution_time
        )
    
    # Log slow requests
    if execution_time > 1000:  # Log if > 1 second
        logger.warning("Slow request detected: %s %s took %.2fms", 
                      request.method, request.url.path, execution_time)
    
    return response

app.include_router(health_router)
app.include_router(flows_router, prefix="/api")
app.include_router(templates_router)

logger.info("Registered routes: health, flows, templates")
logger.info("API endpoints available at /api/flows and /api/flows/templates")


if __name__ == "__main__":  # pragma: no cover - script execution helper
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
