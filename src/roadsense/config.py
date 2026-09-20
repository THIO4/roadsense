"""Application configuration.

All runtime settings come from environment variables (or a local .env file).
The code never hard-codes URLs, keys or hostnames - the *environment* decides,
so the same code/container runs unchanged on a laptop, in CI and in Azure.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Each attribute maps to an env var of the same name (case-insensitive).
    # Values here are safe defaults; anything secret must have NO default.
    digitraffic_base_url: str = "https://tie.digitraffic.fi"
    digitraffic_user: str = "RoadSense-Student/0.1"
    log_level: str = "INFO"

    # --- Azure Cosmos DB ---
    # Optional so that unit tests and --dry-run work without any cloud access.
    # SecretStr hides the value in logs/reprs; call .get_secret_value() to use it.
    cosmos_endpoint: str | None = None  # https://<account>.documents.azure.com:443/
    cosmos_key: SecretStr | None = None
    cosmos_database: str = "roadsense"

    # Read a .env file if present (local dev); real env vars always win over the file.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cosmos_configured(self) -> bool:
        return bool(self.cosmos_endpoint and self.cosmos_key)


@lru_cache
def get_settings() -> Settings:
    """Build settings once and reuse (env vars don't change while the process runs)."""
    return Settings()
