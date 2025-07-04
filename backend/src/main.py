from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import your new router
from src.api.endpoints import validation, trading_partners
from src.core.auth import get_current_user, User

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- Starting up simplified backend service with Keycloak auth ---")
    yield

app = FastAPI(title="EDI Lens Validator API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A protected endpoint to test auth
@app.get("/users/me", response_model=User, tags=["Users"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

# Include our custom application routers
app.include_router(validation.router, prefix="/api/v1/validate", tags=["Validation"])
app.include_router(
    trading_partners.router, 
    prefix="/api/v1/trading-partners", 
    tags=["Trading Partners"]
)

@app.get("/health", tags=["Health"])
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}