"""Shared pytest fixtures.

``backend`` is on ``sys.path`` via ``pythonpath`` in the root
``pyproject.toml``, so ``app.main`` imports directly.

The app under test is backed by an **in-memory SQLite** database (never the
real PostgreSQL configured for runtime). Rather than override ``get_db``, we
patch the module-level engine/session factory in ``app.db.session`` to point
at the in-memory engine — this way BOTH request handlers (via ``get_db``) and
the background library-sync worker (via ``get_session_factory``) share the
exact same database. A single shared connection (``StaticPool``,
``check_same_thread=False``) keeps tables visible across the request thread
and the background-task threadpool.
"""

import os
from collections.abc import Generator

# Provide a deterministic Fernet key for the token-encryption layer BEFORE any
# app module (and its cached Settings) is imported. Real keys live in .env; this
# fixed test key only ever encrypts throwaway in-memory SQLite rows.
os.environ["TOKEN_ENCRYPTION_KEY"] = "gjgpxZr9er1g3w9S08aLeZG_w9GluOzQD0IQ9v-Q1fw="

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as db_session_module
import app.models  # noqa: F401  # register all models on Base.metadata
from app.db.session import Base
from app.main import app


@pytest.fixture()
def _bind_in_memory_db() -> Generator[sessionmaker[Session], None, None]:
    """Point app.db.session at a fresh in-memory SQLite DB for one test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    prev_engine = db_session_module._engine
    prev_factory = db_session_module._session_factory
    db_session_module._engine = engine
    db_session_module._session_factory = factory
    try:
        yield factory
    finally:
        db_session_module._engine = prev_engine
        db_session_module._session_factory = prev_factory
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(_bind_in_memory_db: sessionmaker[Session]) -> TestClient:
    """A TestClient whose handlers + background worker use the in-memory DB.

    BackgroundTasks execute synchronously within the TestClient request cycle,
    so a library-sync job is already ``complete`` by the time ``POST`` returns.
    """
    return TestClient(app)


@pytest.fixture()
def db_session(_bind_in_memory_db: sessionmaker[Session]) -> Generator[Session, None, None]:
    """A direct DB session (same in-memory engine) for seeding rows in tests."""
    db = _bind_in_memory_db()
    try:
        yield db
    finally:
        db.close()
