"""FastAPI application entrypoint for SpaghettiTunes.

Run locally with:
    uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import truststore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Use the OS (Windows/macOS) trust store for TLS verification instead of the
# bundled certifi CA set. Required where a local proxy/antivirus intercepts
# HTTPS with a private root CA (Spotify token exchange otherwise fails with
# CERTIFICATE_VERIFY_FAILED). Runs at import, before any request-time HTTPS.
truststore.inject_into_ssl()

from app.api import auth, generate, health, library, profile
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Bring the database schema up to date on startup via Alembic.

    Alembic is the single source of truth for the schema (incremental,
    reversible migrations — never drop/recreate). Running ``upgrade head`` at
    startup keeps the local dev flow to "just run uvicorn". Tests use a
    ``TestClient`` without a lifespan context, so this does not run there
    (they build tables from ``Base.metadata`` on an in-memory engine).
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]  # app/ -> backend/
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(cfg, "head")
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance.

    Returns:
        FastAPI: A fully-configured app with CORS and all routers mounted.
    """
    settings = get_settings()
    app = FastAPI(
        title="SpaghettiTunes API",
        description="Taste-conditioned music generation backend.",
        version="0.1.0",
        lifespan=lifespan,
    )

    allowed_origins = [o.strip() for o in settings.FRONTEND_ORIGIN.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(library.router)
    app.include_router(profile.router)
    app.include_router(generate.router)

    return app


app = create_app()
