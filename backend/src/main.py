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

origins = ["http://localhost:3000"]

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

# --- THIS IS THE FIX ---
# Keep the main prefix generic and let the endpoint files define their specific paths.
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(validation.router, prefix="/api/v1", tags=["Validation"])
app.include_router(trading_partners.router, prefix="/api/v1", tags=["Trading Partners"])

@app.get("/health", tags=["Health"])
def health_check():
    logger.debug("Health check endpoint was called.")
    return {"status": "ok"}