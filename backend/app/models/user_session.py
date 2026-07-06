"""SQLAlchemy model for authenticated user sessions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedString
from app.db.session import Base


class UserSession(Base):
    """An opaque session mapping to a Spotify user's stored OAuth tokens.

    Attributes:
        session_id: Opaque, random session identifier returned to the
            client by ``/auth/callback``. Primary key.
        spotify_user_id: The authenticated Spotify user's id.
        display_name: The authenticated Spotify user's display name.
        access_token: The current Spotify access token, encrypted at rest
            (Fernet) via :class:`~app.core.crypto.EncryptedString`.
        refresh_token: The Spotify refresh token (encrypted at rest), if one
            was issued.
        expires_at: UTC timestamp of when ``access_token`` expires.
        created_at: UTC timestamp of when the session was created.
    """

    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    spotify_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    access_token: Mapped[str] = mapped_column(EncryptedString(4096), nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedString(4096), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
