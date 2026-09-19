"""Application configuration, loaded from environment variables."""

from functools import lru_cache

from pydantic import field_validator
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
    # ElevenLabs' premade "Bella" voice — a placeholder until Macenplast
    # picks/clones a real voice. NOT "Rachel" (21m00Tcm4TlvDq8ikWAM): as of
    # this writing ElevenLabs gates that specific library voice behind a
    # paid plan ("Free users cannot use library voices via the API", HTTP
    # 402), confirmed against a free-tier account — see ADR 0004. Bella is
    # also a premade/library voice but isn't plan-gated. Override via
    # ELEVENLABS_VOICE_ID.
    elevenlabs_voice_id: str = "hpp4J3VqNfWAUOO0d1Us"

    routing_strategy: str = "serpentine"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_dialect(cls, value: str) -> str:
        """Normalize a plain `postgres://`/`postgresql://` URL (what every
        managed Postgres provider — Neon, Supabase, Heroku-style — hands
        out) to the `postgresql+psycopg://` SQLAlchemy dialect string this
        app's models/session actually need. Leaves already-qualified URLs
        (or any other scheme) untouched."""
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    # INSECURE placeholder — every deployment outside local dev MUST
    # override this via the SECRET_KEY env var. Signs operator auth tokens
    # (see macenplast.security).
    secret_key: str = "dev-only-insecure-secret-change-me"
    access_token_ttl_minutes: int = 480  # one shift

    # Global toggle for the plan's location-label-scan addition (section 1).
    # Per-order/per-line configurability is a plausible future need but
    # isn't modeled yet — flag if the pilot wants it sooner.
    location_check_enabled: bool = True

    # Dev-server origins for the operator PWA (Vite defaults, both loopback
    # spellings since browsers treat them as different origins). Phase 9's
    # production deployment serves both behind one Caddy origin instead, so
    # this won't matter there — see docs/adr for the deployment decision.
    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide `Settings` instance, cached after first call."""
    return Settings()
