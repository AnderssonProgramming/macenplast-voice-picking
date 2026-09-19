"""Application configuration, loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API.

    All values have safe local-dev defaults; production deployments
    override them via environment variables (see `.env.example`).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "macenplast-voice-picking"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://macenplast:macenplast@localhost:5432/macenplast"

    elevenlabs_api_key: str = ""
    voice_clip_dir: str = "./voice_clips"

    routing_strategy: str = "serpentine"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide `Settings` instance, cached after first call."""
    return Settings()
