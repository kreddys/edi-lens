from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from src.api.endpoints import validation, trading_partners, auth
from src.core.auth import get_current_user, User
from src.core.config import setup_logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("--- Starting up EDI Lens Validator API ---")
    yield
    logger.info("--- Shutting down EDI Lens Validator API ---")


app = FastAPI(title="EDI Lens Validator API", lifespan=lifespan)

# Add the new admin UI's origin to the list
origins = [
    "http://localhost:5173", # Existing Vite frontend
    "http://localhost:3000", # New Admin UI
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/users/me", response_model=User, tags=["Users"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    logger.info(f"User {current_user.username} fetched their profile.")
    return current_user

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

app.include_router(validation.router, prefix="/api/v1/validate", tags=["Validation"])
app.include_router(
    trading_partners.router,
    prefix="/api/v1/trading-partners",
    tags=["Trading Partners"]
)

@app.get("/health", tags=["Health"])
def health_check():
    """Simple health check endpoint."""
    logger.debug("Health check endpoint was called.")
    return {"status": "ok"}