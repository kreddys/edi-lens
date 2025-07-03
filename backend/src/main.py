from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.core.database import init_db
from src.api.endpoints import validation

# Define an async context manager for application lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    print("--- Starting up backend service ---")
    await init_db()
    print("--- Database initialized ---")
    yield
    # Code to run on shutdown
    print("--- Shutting down backend service ---")


app = FastAPI(
    title="EDI Lens Validator API",
    lifespan=lifespan
)

# Configure CORS
# In a production environment, you should restrict the origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for now
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include API routers
app.include_router(validation.router, prefix="/api/v1", tags=["Validation"])

@app.get("/health", tags=["Health"])
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}