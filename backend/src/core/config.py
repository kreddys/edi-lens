import logging
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from keycloak import KeycloakOpenID
from pathlib import Path

# --- THIS IS THE FIX ---
# Calculate the project root directory relative to this file's location.
# This file is in: /backend/src/core/
# We need to go up three levels to get to the project root.
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Define the explicit paths to the environment files.
ENV_FILE_LOCAL_PATH = PROJECT_ROOT / ".env.local"
ENV_FILE_PROD_PATH = PROJECT_ROOT / ".env"


# --- Settings Model (with LOG_LEVEL) ---
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
    # Directory for storing EDI implementation guide schemas
    EDI_SCHEMA_DIRECTORY: str = "/home/appuser/app/data/edi_schemas"

    REMOTE_HOST: str = "localhost"
    BACKEND_HOST: str = "backend"    

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Configure the model to load from an env file and to ignore extra variables.
    # We now provide the absolute paths to the environment files.
    model_config = SettingsConfigDict(
        env_file=(str(ENV_FILE_LOCAL_PATH), str(ENV_FILE_PROD_PATH)),
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()

# --- Logging Setup Function (Correct) ---
def setup_logging():
    """Configures the root logger for the application."""
    log_level = settings.LOG_LEVEL.upper()
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    logging.getLogger("uvicorn").handlers.clear()
    logging.getLogger("uvicorn.error").propagate = True
    logging.getLogger("uvicorn.access").propagate = True

    logging.getLogger(__name__).info(f"Logging configured with level: {log_level}")

# --- Keycloak Client Initialization (Correct) ---
# This client is ONLY used for server-to-server communication (in the callback).
# The browser-facing URL is constructed manually in the /login endpoint.
keycloak_openid = KeycloakOpenID(
    server_url=settings.KEYCLOAK_URL,
    realm_name=settings.KEYCLOAK_REALM,
    client_id=settings.KEYCLOAK_BACKEND_CLIENT_ID,
    client_secret_key=settings.KEYCLOAK_BACKEND_CLIENT_SECRET
)