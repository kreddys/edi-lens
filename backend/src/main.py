"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes.health import router as health_router
from .core.config import settings
from .core.database import dispose_engine

app = FastAPI(
    title="EDI Lens NiFi Backend",
    description="Minimal NiFi workflow management backend",
    version=settings.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Ensure database resources are released on app shutdown."""

    await dispose_engine()


if __name__ == "__main__":  # pragma: no cover - script execution helper
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
