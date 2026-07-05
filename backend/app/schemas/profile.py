"""Pydantic schemas for the /profile/* endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class ProfileBuildRequest(BaseModel):
    """Request body for ``POST /profile/build``."""

    session_id: str = Field(..., description="Session id returned by /auth/callback.")


class ProfileBuildResponse(BaseModel):
    """Response for ``POST /profile/build``."""

    profile_id: str
    status: Literal["building", "ready"]


class ProfileSummary(BaseModel):
    """High-level statistics for a user's taste profile."""

    top_genres: list[str]
    track_count: int = Field(..., ge=0)
    eclecticness: float = Field(
        ..., ge=0.0, le=1.0, description="0 = very focused taste, 1 = highly eclectic."
    )


class Cluster(BaseModel):
    """A single taste cluster derived from k-means/GMM clustering."""

    label: str
    size: int = Field(..., ge=0)
    descriptor: str = Field(..., description="Human-readable summary, e.g. 'energetic electronic'.")


class Point(BaseModel):
    """A single 2-D projected point for the taste-map visualization."""

    x: float
    y: float
    label: str


class ProfileResponse(BaseModel):
    """Response for ``GET /profile``."""

    summary: ProfileSummary
    clusters: list[Cluster]
    viz: list[Point]
