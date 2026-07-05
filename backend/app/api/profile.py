"""Taste-profile endpoints.

Phase 0: typed STUBS only. Real feature aggregation, clustering
(k-means/GMM), and PCA/UMAP projection land in Phase 2.
"""

import uuid

from fastapi import APIRouter, Query

from app.schemas.profile import (
    Cluster,
    Point,
    ProfileBuildRequest,
    ProfileBuildResponse,
    ProfileResponse,
    ProfileSummary,
)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/build", response_model=ProfileBuildResponse)
def build_profile(payload: ProfileBuildRequest) -> ProfileBuildResponse:
    """Kick off taste-profile computation for a session.

    Stub: synchronously returns a "ready" profile id rather than enqueuing
    real clustering work.

    Args:
        payload: Request body carrying the session to build a profile for.

    Returns:
        ProfileBuildResponse: A freshly-minted profile id and its status.
    """
    return ProfileBuildResponse(profile_id=f"prof_{uuid.uuid4().hex[:12]}", status="ready")


@router.get("", response_model=ProfileResponse)
def get_profile(
    session_id: str = Query(..., description="Session id returned by /auth/callback."),
) -> ProfileResponse:
    """Return the taste-profile summary, clusters, and 2-D viz points.

    Stub: returns fixed placeholder data regardless of ``session_id``.

    Args:
        session_id: The session to fetch a profile for.

    Returns:
        ProfileResponse: Placeholder summary stats, taste clusters, and
        2-D projected points for the UI's taste map.
    """
    summary = ProfileSummary(
        top_genres=["indie pop", "electronic", "lo-fi"],
        track_count=317,
        eclecticness=0.42,
    )
    clusters = [
        Cluster(label="Cluster A", size=120, descriptor="energetic electronic with driving synths"),
        Cluster(label="Cluster B", size=95, descriptor="mellow acoustic singer-songwriter"),
        Cluster(label="Cluster C", size=102, descriptor="upbeat indie pop"),
    ]
    viz = [
        Point(x=0.12, y=0.44, label="Cluster A"),
        Point(x=-0.31, y=0.18, label="Cluster B"),
        Point(x=0.52, y=-0.09, label="Cluster C"),
    ]
    return ProfileResponse(summary=summary, clusters=clusters, viz=viz)
