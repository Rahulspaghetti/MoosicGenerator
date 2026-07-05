"""SQLAlchemy model tracking an asynchronous library-sync job."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LibrarySyncJob(Base):
    """State for one background ``/library/sync`` ingestion job.

    ``POST /library/sync`` creates a row (``pending``) and schedules a
    background task; the worker flips it to ``running``, updates
    ``processed``/``total`` as it throttles through artist lookups, and
    finally writes the serialized :class:`~app.schemas.library.LibrarySyncResponse`
    into ``result`` (``complete``) or an ``error`` (``failed``).
    ``GET /library/sync/{job_id}`` polls this row.

    Attributes:
        job_id: Opaque job identifier. Primary key.
        session_id: The user session this sync belongs to.
        status: One of ``pending`` | ``running`` | ``complete`` | ``failed``.
        processed: Number of unique artists resolved so far.
        total: Total unique artists to resolve (0 until known).
        result: JSON-encoded ``LibrarySyncResponse`` once ``complete``.
        error: Human-readable failure reason once ``failed``.
        created_at: UTC timestamp of when the job was enqueued.
        updated_at: UTC timestamp of the last status/progress update.
    """

    __tablename__ = "library_sync_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Partial fingerprint, surfaced while the job is still running so the UI can
    # open the prompt screen before the full sync finishes. server_default keeps
    # inserts valid even if an older model revision omits the column.
    liked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    partial_genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
