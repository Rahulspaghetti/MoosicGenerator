"""Liveness endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return a static liveness payload.

    Returns:
        A ``{"status": "ok"}`` dict, used by Docker healthchecks / uptime probes.
    """
    return {"status": "ok"}
