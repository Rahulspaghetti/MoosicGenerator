"""Pydantic schemas for the /library/* endpoints."""

from pydantic import BaseModel, Field


class SyncRequest(BaseModel):
    """Request body for ``POST /library/sync``."""

    session_id: str = Field(..., description="Session id returned by /auth/callback.")
    force: bool = Field(
        default=False, description="Re-sync even if a fresh stored profile exists."
    )


class Playlist(BaseModel):
    """A single Spotify playlist summary."""

    id: str
    name: str
    tracks: int = Field(..., ge=0, description="Track count in the playlist.")
    color: str = Field(..., description="Hex color used by the UI to render the playlist card.")


class LibrarySyncResponse(BaseModel):
    """The finished library-sync payload (embedded in the job result)."""

    liked_count: int = Field(..., ge=0, description="Total Liked Songs ingested.")
    playlists: list[Playlist]
    genres: list[str] = Field(..., description="Deduped genre tags aggregated from artist metadata.")
    synced_at: str = Field(..., description="ISO 8601 timestamp of when the sync completed.")


class LibrarySyncJobResponse(BaseModel):
    """Response for ``POST /library/sync`` — the enqueued job handle."""

    job_id: str = Field(..., description="Poll GET /library/sync/{job_id} for progress/result.")
    status: str = Field(..., description="Job status; always 'pending' at creation.")


class LibrarySyncStartResponse(BaseModel):
    """Response for ``POST /library/sync``.

    Either serves a fresh stored profile immediately (``cached=True``) or
    enqueues a background sync job to poll (``cached=False`` + ``job_id``).
    """

    cached: bool = Field(..., description="True when a fresh stored profile was served.")
    status: str = Field(..., description="'cached' | 'pending'.")
    job_id: str | None = Field(default=None, description="Poll target when not cached.")
    profile: LibrarySyncResponse | None = Field(
        default=None, description="The stored fingerprint when cached."
    )


class LibrarySyncStatusResponse(BaseModel):
    """Response for ``GET /library/sync/{job_id}``.

    ``liked_count`` and ``genres`` form the *partial fingerprint* — populated
    while the job is still ``running`` so the UI can open the prompt screen
    before the full sync finishes. ``result`` holds the complete payload once
    ``status`` is ``complete``.
    """

    job_id: str
    status: str = Field(..., description="pending | running | complete | failed.")
    processed: int = Field(..., ge=0, description="Unique artists resolved so far.")
    total: int = Field(..., ge=0, description="Total unique artists to resolve (0 until known).")
    liked_count: int = Field(0, ge=0, description="Liked Songs counted so far (partial fingerprint).")
    genres: list[str] = Field(
        default_factory=list, description="Genres aggregated so far (partial fingerprint)."
    )
    result: LibrarySyncResponse | None = Field(
        default=None, description="Present only when status is 'complete'."
    )
    error: str | None = Field(default=None, description="Present only when status is 'failed'.")
