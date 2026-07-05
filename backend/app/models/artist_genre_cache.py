"""SQLAlchemy model caching Spotify artist-id -> genres lookups."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ArtistGenreCache(Base):
    """Write-through cache of a Spotify artist's genre tags.

    Populated by ``POST /library/sync`` so repeat syncs (or overlapping
    listeners) never re-fetch genres for an artist already looked up.

    Attributes:
        artist_id: The Spotify artist id. Primary key.
        genres: JSON-encoded ``list[str]`` of genre tags. Stored as text
            (rather than a native JSON column) so the same model works
            unchanged against both SQLite (tests) and PostgreSQL (prod).
        fetched_at: UTC timestamp of when the genres were fetched.
    """

    __tablename__ = "artist_genre_cache"

    artist_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    genres: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
