"""Application configuration loaded from environment variables / .env.

All secrets and environment-specific values live here, sourced via
``pydantic-settings``. Never hardcode credentials elsewhere in the app.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env, resolved absolutely so it loads regardless of the process CWD
# (uvicorn is typically launched from backend/, pytest from the repo root). In a
# container this path won't exist; secrets are injected as real env vars there,
# which pydantic-settings reads with higher priority anyway.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Typed application settings.

    Attributes:
        SPOTIFY_CLIENT_ID: OAuth client id issued by Spotify's developer dashboard.
        SPOTIFY_CLIENT_SECRET: OAuth client secret. Server-side only, never sent
            to the browser (PKCE keeps the browser secret-free regardless).
        SPOTIFY_REDIRECT_URI: The callback URI registered with Spotify.
        RECCOBEATS_API_KEY: API key for the ReccoBeats audio-feature enrichment
            service (optional enrichment layer, see Phase 1/2).
        HF_TOKEN: Hugging Face access token for gated model downloads.
        DATABASE_URL: SQLAlchemy connection string for PostgreSQL.
        REDIS_URL: Connection string for Redis, used as the Celery broker
            and result backend.
        FRONTEND_ORIGIN: Comma-separated list of browser origins allowed by
            CORS. Defaults to the Angular dev server on both loopback spellings
            so the app works whether opened at 127.0.0.1 or localhost.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""
    # The browser is redirected here by Spotify after consent. This is the
    # FRONTEND's /callback route (Angular), which reads code/state and calls
    # the backend's GET /auth/callback via XHR. Spotify requires 127.0.0.1
    # (not "localhost") for http loopback redirect URIs, and it must be
    # registered verbatim on the Spotify app + browsed on this same origin
    # (sessionStorage CSRF state is per-origin).
    SPOTIFY_REDIRECT_URI: str = "http://127.0.0.1:4200/callback"
    RECCOBEATS_API_KEY: str = ""
    HF_TOKEN: str = ""
    DATABASE_URL: str = (
        "postgresql+psycopg://spaghettitunes:spaghettitunes@localhost:5432/spaghettitunes"
    )
    REDIS_URL: str = "redis://redis:6379/0"
    FRONTEND_ORIGIN: str = "http://127.0.0.1:4200,http://localhost:4200"
    # A stored taste profile is served without re-syncing while it is younger
    # than this many days; older (or a forced request) triggers a background refresh.
    PROFILE_TTL_DAYS: int = 14


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide :class:`Settings` instance.

    Cached via ``lru_cache`` so environment parsing happens once per process
    while still remaining easily overridable/mockable in tests via
    ``get_settings.cache_clear()``.
    """
    return Settings()
