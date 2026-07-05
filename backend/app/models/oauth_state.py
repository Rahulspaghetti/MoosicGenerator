"""SQLAlchemy model for transient PKCE OAuth ``state`` values."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OAuthState(Base):
    """A single-use CSRF ``state`` value tied to its PKCE ``code_verifier``.

    Rows are created by ``GET /auth/login`` and consumed by
    ``GET /auth/callback`` to recover the ``code_verifier`` needed to
    complete the PKCE token exchange.

    Attributes:
        state: The random, URL-safe CSRF token issued to the browser.
            Primary key.
        code_verifier: The PKCE code verifier generated alongside ``state``.
        created_at: UTC timestamp of when the row was created.
    """

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    code_verifier: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
