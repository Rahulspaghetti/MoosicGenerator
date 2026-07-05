"""Library ingestion — asynchronous, rate-limited.

``POST /library/sync`` enqueues a background job and returns immediately with
a ``job_id``. A background task (FastAPI ``BackgroundTasks``) then ingests the
user's Liked Songs and aggregates artist genres **gently**: a small delay
between artist lookups plus exponential backoff on HTTP 429 keeps us under
Spotify's rate limit, and artists that keep failing are skipped rather than
failing the whole sync. ``GET /library/sync/{job_id}`` polls progress/result.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from itertools import cycle
from typing import Any

import spotipy
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db, get_session_factory
from app.models import ArtistGenreCache, LibrarySyncJob, TasteProfile, UserSession
from app.schemas.library import (
    LibrarySyncResponse,
    LibrarySyncStartResponse,
    LibrarySyncStatusResponse,
    Playlist,
    SyncRequest,
)

router = APIRouter(prefix="/library", tags=["library"])
logger = logging.getLogger("app.library")

_PAGE_SIZE = 50
# Rate control: pause between per-artist lookups so we stay under Spotify's
# rolling rate limit instead of bursting into 429s.
_REQUEST_DELAY_S = 0.2
# 429 handling: exponential backoff, capped, then skip the artist.
_MAX_ATTEMPTS = 6
_BACKOFF_BASE_S = 1.0
_BACKOFF_CAP_S = 30.0
# Persist progress every N artists so polling sees movement without a write per artist.
_PROGRESS_COMMIT_EVERY = 5
_PLAYLIST_COLORS: list[str] = ["#FF6B6B", "#4ECDC4", "#FFE66D", "#A78BFA", "#34D399", "#F472B6"]


def _collect_liked_tracks(sp: spotipy.Spotify) -> tuple[int, set[str]]:
    """Paginate through Liked Songs, 50 per page, following the ``next`` cursor.

    Best-effort: if a page fails (rate limit, transient error), stop and return
    whatever was collected so far rather than aborting the whole sync — the
    partial fingerprint is still useful.

    Returns:
        A tuple of ``(liked track count so far, unique artist ids)``.
    """
    seen = 0
    reported_total: int | None = None
    artist_ids: set[str] = set()
    try:
        page: dict[str, Any] | None = sp.current_user_saved_tracks(limit=_PAGE_SIZE)
        while page is not None:
            if reported_total is None:
                reported_total = page.get("total")
            items = page.get("items") or []
            seen += len(items)
            for item in items:
                track = (item or {}).get("track") or {}
                for artist in track.get("artists") or []:
                    artist_id = artist.get("id")
                    if artist_id:
                        artist_ids.add(artist_id)
            page = sp.next(page) if page.get("next") else None
    except Exception as exc:  # noqa: BLE001 - best-effort; keep the partial haul
        logger.warning("liked-tracks pagination stopped early: %r", exc)
    # Prefer Spotify's authoritative total; fall back to what we actually counted.
    liked_count = reported_total if reported_total is not None else seen
    return liked_count, artist_ids


def _retry_after_seconds(exc: spotipy.SpotifyException, default: float) -> float:
    """Read the ``Retry-After`` header off a 429 exception, else fall back.

    spotipy often strips the header (routing 429s through its urllib3 Retry
    path), so ``default`` — an exponential backoff — is the common case.
    """
    headers = getattr(exc, "headers", None) or {}
    raw = headers.get("Retry-After")
    try:
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _fetch_artist_genres(sp: spotipy.Spotify, artist_id: str) -> list[str]:
    """Fetch an artist's genres, backing off on HTTP 429.

    On 429 it sleeps (``Retry-After`` if present, otherwise exponential
    backoff capped at :data:`_BACKOFF_CAP_S`) and retries up to
    :data:`_MAX_ATTEMPTS`. Non-429 errors, or an exhausted retry budget,
    propagate to the caller (which skips the artist).
    """
    attempt = 0
    while True:
        try:
            artist = sp.artist(artist_id)
            return list(artist.get("genres") or [])
        except spotipy.SpotifyException as exc:
            attempt += 1
            if exc.http_status != 429 or attempt >= _MAX_ATTEMPTS:
                raise
            backoff = min(_BACKOFF_BASE_S * (2 ** (attempt - 1)), _BACKOFF_CAP_S)
            time.sleep(_retry_after_seconds(exc, default=backoff))


def _resolve_genres(
    db: Session, sp: spotipy.Spotify, artist_ids: list[str], job: LibrarySyncJob
) -> set[str]:
    """Resolve genres for every artist via a write-through cache, throttled.

    Cache hits cost no HTTP call. Cache misses fetch with backoff, then pause
    :data:`_REQUEST_DELAY_S` to stay under the rate limit. An artist that
    still fails is skipped (not cached), so a later sync can retry it. Job
    ``processed`` is committed every :data:`_PROGRESS_COMMIT_EVERY` artists.
    """
    genres: set[str] = set()
    for index, artist_id in enumerate(artist_ids, start=1):
        cached = db.get(ArtistGenreCache, artist_id)
        if cached is not None:
            genres.update(json.loads(cached.genres))
        else:
            try:
                fetched = _fetch_artist_genres(sp, artist_id)
            except spotipy.SpotifyException as exc:
                logger.warning("skipping artist %s after retries: %r", artist_id, exc)
            else:
                genres.update(fetched)
                db.add(
                    ArtistGenreCache(
                        artist_id=artist_id,
                        genres=json.dumps(fetched),
                        fetched_at=datetime.now(UTC),
                    )
                )
                db.commit()
                time.sleep(_REQUEST_DELAY_S)

        job.processed = index
        if index % _PROGRESS_COMMIT_EVERY == 0:
            job.partial_genres = json.dumps(sorted(genres))
            db.commit()
    job.partial_genres = json.dumps(sorted(genres))
    db.commit()
    return genres


def _collect_playlists(sp: spotipy.Spotify) -> list[Playlist]:
    """Best-effort fetch of the user's playlists; degrades to ``[]`` on error."""
    playlists: list[Playlist] = []
    try:
        page: dict[str, Any] | None = sp.current_user_playlists(limit=_PAGE_SIZE)
        colors = cycle(_PLAYLIST_COLORS)
        while page is not None:
            for item in page.get("items") or []:
                playlists.append(
                    Playlist(
                        id=item["id"],
                        name=item.get("name", ""),
                        tracks=(item.get("tracks") or {}).get("total", 0),
                        color=next(colors),
                    )
                )
            page = sp.next(page) if page.get("next") else None
    except Exception:  # noqa: BLE001 - best-effort; never fail the sync over this
        return playlists
    return playlists


def _run_library_sync(job_id: str) -> None:
    """Background worker: ingest the library for ``job_id`` and record results.

    Runs with its own DB session (the request-scoped one is long gone by the
    time this executes after the response). Flips the job to ``running``,
    resolves genres with throttling, and writes ``complete`` (+ result) or
    ``failed`` (+ error).
    """
    db: Session = get_session_factory()()
    try:
        job = db.get(LibrarySyncJob, job_id)
        if job is None:
            return
        session = db.get(UserSession, job.session_id)
        if session is None:
            job.status, job.error = "failed", "Unknown session_id."
            db.commit()
            return

        job.status = "running"
        db.commit()

        sp = spotipy.Spotify(auth=session.access_token, retries=0, status_retries=0)
        liked_count, artist_ids = _collect_liked_tracks(sp)
        ordered_ids = sorted(artist_ids)
        job.liked_count = liked_count
        job.total = len(ordered_ids)
        db.commit()

        genres = _resolve_genres(db, sp, ordered_ids, job)
        playlists = _collect_playlists(sp)

        result = LibrarySyncResponse(
            liked_count=liked_count,
            playlists=playlists,
            genres=sorted(genres),
            synced_at=datetime.now(UTC).isoformat(),
        )
        job.result = result.model_dump_json()
        job.status = "complete"

        # Persist the fingerprint per user so future logins reuse it (no re-sync).
        _upsert_taste_profile(db, session.spotify_user_id, result)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - record failure on the job, don't crash the worker
        logger.exception("library sync job %s failed", job_id)
        db.rollback()
        job = db.get(LibrarySyncJob, job_id)
        if job is not None:
            job.status, job.error = "failed", str(exc)
            db.commit()
    finally:
        db.close()


def _profile_to_response(profile: TasteProfile) -> LibrarySyncResponse:
    """Render a stored :class:`TasteProfile` as the library payload the UI expects."""
    synced = profile.synced_at
    if synced.tzinfo is None:
        synced = synced.replace(tzinfo=UTC)
    return LibrarySyncResponse(
        liked_count=profile.liked_count,
        playlists=[Playlist(**p) for p in json.loads(profile.playlists or "[]")],
        genres=json.loads(profile.genres or "[]"),
        synced_at=synced.isoformat(),
    )


def _upsert_taste_profile(db: Session, spotify_user_id: str, result: LibrarySyncResponse) -> None:
    """Insert or update the durable per-user fingerprint from a sync result."""
    profile = db.get(TasteProfile, spotify_user_id)
    if profile is None:
        profile = TasteProfile(spotify_user_id=spotify_user_id, synced_at=datetime.now(UTC))
        db.add(profile)
    profile.liked_count = result.liked_count
    profile.genres = json.dumps(result.genres)
    profile.playlists = json.dumps([p.model_dump() for p in result.playlists])
    profile.synced_at = datetime.now(UTC)


def _is_profile_fresh(profile: TasteProfile, ttl_days: int) -> bool:
    """True if the profile was synced within ``ttl_days`` (tz-normalized)."""
    synced = profile.synced_at
    if synced.tzinfo is None:
        synced = synced.replace(tzinfo=UTC)
    return synced > datetime.now(UTC) - timedelta(days=ttl_days)


@router.post("/sync", response_model=LibrarySyncStartResponse)
def sync_library(
    payload: SyncRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> LibrarySyncStartResponse:
    """Serve the stored fingerprint if fresh, else enqueue a background sync.

    When a fresh :class:`TasteProfile` exists (and ``force`` is false), returns
    it immediately (``cached=True``) so the caller skips syncing. Otherwise
    starts a background job and returns a ``job_id`` to poll.

    Raises:
        HTTPException: 404 if ``session_id`` does not match a known session.
    """
    session = db.get(UserSession, payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown session_id.")

    profile = db.get(TasteProfile, session.spotify_user_id)
    ttl_days = get_settings().PROFILE_TTL_DAYS
    if profile is not None and not payload.force and _is_profile_fresh(profile, ttl_days):
        return LibrarySyncStartResponse(
            cached=True, status="cached", job_id=None, profile=_profile_to_response(profile)
        )

    job_id = f"lib_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}_{payload.session_id[-6:]}"
    db.add(LibrarySyncJob(job_id=job_id, session_id=payload.session_id, status="pending"))
    db.commit()

    background_tasks.add_task(_run_library_sync, job_id)
    return LibrarySyncStartResponse(cached=False, status="pending", job_id=job_id, profile=None)


@router.get(
    "/profile",
    response_model=LibrarySyncResponse,
    responses={404: {"description": "No stored profile for this session's user."}},
)
def get_profile(session_id: str, db: Session = Depends(get_db)) -> LibrarySyncResponse:
    """Return the durable stored fingerprint for a session's user.

    Raises:
        HTTPException: 404 if the session or the user's profile is unknown.
    """
    session = db.get(UserSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown session_id.")
    profile = db.get(TasteProfile, session.spotify_user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No stored taste profile yet.")
    return _profile_to_response(profile)


@router.get("/sync/{job_id}", response_model=LibrarySyncStatusResponse)
def get_sync_status(job_id: str, db: Session = Depends(get_db)) -> LibrarySyncStatusResponse:
    """Poll a library-sync job's status/progress/result.

    Raises:
        HTTPException: 404 if ``job_id`` is unknown.
    """
    job = db.get(LibrarySyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'.")

    result = (
        LibrarySyncResponse.model_validate_json(job.result)
        if job.status == "complete" and job.result
        else None
    )
    genres = result.genres if result else (json.loads(job.partial_genres) if job.partial_genres else [])
    return LibrarySyncStatusResponse(
        job_id=job.job_id,
        status=job.status,
        processed=job.processed,
        total=job.total,
        liked_count=job.liked_count,
        genres=genres,
        result=result,
        error=job.error,
    )
