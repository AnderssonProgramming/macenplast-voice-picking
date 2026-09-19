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

    # Port 5442: host-side default, matching docker-compose.yml's mapping
    # (5432-5434 are taken by native Postgres installs on this machine;
    # inside Docker, the api container reaches Postgres at postgres:5432
    # instead, via the DATABASE_URL env var set in docker-compose.yml).
    database_url: str = "postgresql+psycopg://macenplast:macenplast@localhost:5442/macenplast"

    elevenlabs_api_key: str = ""
    # ElevenLabs' public "Rachel" voice — a placeholder until Macenplast
    # picks/clones a real voice. Override via ELEVENLABS_VOICE_ID.
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    voice_clip_dir: str = "./voice_clips"

    routing_strategy: str = "serpentine"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide `Settings` instance, cached after first call."""
    return Settings()
