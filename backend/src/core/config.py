import logging
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from keycloak import KeycloakOpenID
from pathlib import Path

# The Settings class now cleanly reads from the process environment,
# which should be populated by the entrypoint script (e.g., run_crew.py or a uvicorn startup script)
# before this module is imported.

class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    API_V1_STR: str = "/api/v1"

    KEYCLOAK_URL: str
    KEYCLOAK_BROWSER_URL: str
    KEYCLOAK_REALM: str
    KEYCLOAK_BACKEND_CLIENT_ID: str
    KEYCLOAK_BACKEND_CLIENT_SECRET: str
    
    LOG_LEVEL: str = "INFO"
    EDI_SCHEMA_DIRECTORY: str = "/home/appuser/app/data/edi_schemas"
    REMOTE_HOST: str = "localhost"
    BACKEND_HOST: str = "backend"    

    PINECONE_API_KEY: str = ""
    PINECONE_EMBED_MODEL: str = "multilingual-e5-large"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Simplified config - it will read from the environment by default.
    # The responsibility of loading a .env file is now on the script that runs the app.
    model_config = SettingsConfigDict(extra='ignore')


# This line will now succeed because the entrypoint script is expected to
# have already populated the environment using `load_dotenv`.
settings = Settings()


def setup_logging():
    """Configures the root logger based on the LOG_LEVEL from the loaded settings."""
    log_level = settings.LOG_LEVEL.upper()
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
        stream=sys.stdout,
        force=True, 
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {log_level}")
    
    # Configure uvicorn loggers to use the root configuration
    logging.getLogger("uvicorn").handlers.clear()
    logging.getLogger("uvicorn.error").propagate = True
    logging.getLogger("uvicorn.access").propagate = True

# --- Keycloak Client Initialization ---
keycloak_openid = KeycloakOpenID(
    server_url=settings.KEYCLOAK_URL,
    realm_name=settings.KEYCLOAK_REALM,
    client_id=settings.KEYCLOAK_BACKEND_CLIENT_ID,
    client_secret_key=settings.KEYCLOAK_BACKEND_CLIENT_SECRET
)