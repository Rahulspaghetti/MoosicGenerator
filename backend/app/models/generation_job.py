"""SQLAlchemy model tracking an asynchronous music-generation job."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GenerationJob(Base):
    """State for one background ``/generate`` job.

    ``POST /generate`` creates a row (``pending``) and schedules a background
    task; the worker flips it to ``running``, runs MusicGen inference, transcodes
    the result to MP3, and writes ``complete`` (+ ``audio_path``) or ``failed``
    (+ ``error``). ``GET /generate/{job_id}`` polls this row and
    ``GET /generate/{job_id}/audio`` streams the finished file.

    Attributes:
        job_id: Opaque job identifier. Primary key.
        session_id: The user session that requested the generation.
        prompt: The free-text prompt conditioning the generation.
        status: One of ``pending`` | ``running`` | ``complete`` | ``failed``.
        progress: 0.0–1.0 coarse progress for the UI.
        step: Human-readable current pipeline stage.
        audio_path: Absolute path to the rendered MP3 once ``complete``.
        error: Human-readable failure reason once ``failed``.
        created_at: UTC timestamp of when the job was enqueued.
        updated_at: UTC timestamp of the last status/progress update.
    """

    __tablename__ = "generation_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
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
