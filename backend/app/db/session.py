"""SQLAlchemy engine/session wiring.

Deliberately lazy: the engine is not constructed at import time, so
importing this module (or the app) never requires network access to
PostgreSQL or the ``psycopg`` driver to be installed. This keeps the Phase 0
stub endpoints (which do not touch the database) importable and testable
offline. Real persistence lands in later phases.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Lazily create (once) and return the SQLAlchemy engine.

    Returns:
        The process-wide SQLAlchemy :class:`Engine`, built from
        ``settings.DATABASE_URL`` on first use.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the lazily-constructed session factory bound to :func:`get_engine`."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, future=True
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session.

    Not wired into any Phase 0 route (all endpoints are stubs). Intended for
    use via ``Depends(get_db)`` once real persistence is implemented.
    """
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
