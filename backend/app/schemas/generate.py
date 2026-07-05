"""Pydantic schemas for the /generate endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Request body for ``POST /generate``."""

    session_id: str = Field(..., description="Session id returned by /auth/callback.")
    prompt: str = Field(..., min_length=1, description="Free-text generation prompt.")
    lyrics: str | None = Field(default=None, description="Optional user-supplied lyrics.")
    enhance_lyrics: bool = Field(
        default=False, description="If true, an LLM pass polishes/expands the supplied lyrics."
    )
    reference_sample_ids: list[str] = Field(
        default_factory=list,
        description="Optional ids of reference tracks/clusters to condition generation on.",
    )


class GenerateResponse(BaseModel):
    """Response for ``POST /generate`` (HTTP 202)."""

    job_id: str
    status: Literal["pending"] = "pending"


class GenerateStatusResponse(BaseModel):
    """Response for ``GET /generate/{job_id}``."""

    job_id: str
    status: Literal["pending", "running", "complete", "failed"]
    progress: float = Field(..., ge=0.0, le=1.0)
    step: str | None = Field(default=None, description="Human-readable current pipeline step.")
    url: str | None = Field(default=None, description="MP3 URL, populated once status is 'complete'.")
    error: str | None = Field(default=None, description="Error message, populated when status is 'failed'.")
