from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from src.api.endpoints import validation, trading_partners, auth, schemas # Add schemas
from src.core.auth import get_current_user, User
from src.core.config import setup_logging
from src.core.audit import before_flush, after_flush_postexec
from src.core.schema_manager import schema_manager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("--- Starting up EDI Lens Validator API ---")
    
    # Load all EDI implementation guide schemas into memory on startup.
    schema_dir = Path(__file__).parent / "edi_schemas"
    schema_manager.load_schemas(schema_dir)
    
    logger.info("Audit logging system initialized.")
    yield
    logger.info("--- Shutting down EDI Lens Validator API ---")

app = FastAPI(
    title="EDI Lens Validator API",
    description="Backend API for the EDI Lens application, handling EDI validation, trading partner configuration, and user authentication.",
    version="1.0.0",
    lifespan=lifespan
)

origins = ["http://localhost:3000", "http://localhost:3001"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/users/me", response_model=User, tags=["Users"], summary="Get Current User",
         description="Fetches the profile information for the currently authenticated user based on their JWT.")
async def read_users_me(current_user: User = Depends(get_current_user)):
    logger.info(f"User {current_user.username} fetched their profile.")
    return current_user

app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(validation.router, prefix="/api/v1", tags=["Validation"])
app.include_router(trading_partners.router, prefix="/api/v1", tags=["Trading Partners"])
app.include_router(schemas.router, prefix="/api/v1", tags=["Schemas"]) # ADD THIS LINE

@app.get("/health", tags=["Health"], summary="Health Check",
         description="A simple endpoint to verify that the API service is running and responsive.")
def health_check():
    logger.debug("Health check endpoint was called.")
    return {"status": "ok"}
