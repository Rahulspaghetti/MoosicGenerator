"""SQLAlchemy model persisting a user's taste fingerprint across sessions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TasteProfile(Base):
    """A user's taste fingerprint, keyed by their (stable) Spotify user id.

    Written by the library-sync worker on completion and reused on subsequent
    logins so we don't re-sync every time. Sessions are ephemeral; this row is
    the durable, per-user record. Phase 2 extends it with feature vectors,
    clusters, and embeddings.

    Attributes:
        spotify_user_id: The authenticated Spotify user's id. Primary key —
            stable across logins/sessions.
        liked_count: Total Liked Songs (Spotify-reported), also used as a cheap
            change signal.
        genres: JSON-encoded ``list[str]`` of aggregated genre tags.
        playlists: JSON-encoded ``list[Playlist]`` for the UI.
        synced_at: UTC timestamp of the last successful full sync (freshness).
        created_at/updated_at: audit timestamps.
    """

    __tablename__ = "taste_profiles"

    spotify_user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    liked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    genres: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    playlists: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
