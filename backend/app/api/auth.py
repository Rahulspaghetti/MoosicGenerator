"""Spotify OAuth (Authorization Code + PKCE) endpoints.

Phase 1: real PKCE ``code_verifier``/``code_challenge`` generation and a
real token exchange with Spotify via spotipy's ``SpotifyPKCE`` auth
manager. No token is ever cached to disk -- every auth manager instance
uses a fresh, request-scoped :class:`~spotipy.cache_handler.MemoryCacheHandler`.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime

import spotipy
from fastapi import APIRouter, Depends, HTTPException, Query
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyOauthError, SpotifyPKCE
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import OAuthState, UserSession
from app.schemas.auth import AuthCallbackResponse, AuthError, AuthLoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

_SCOPE = "user-library-read"


def _build_pkce_manager(code_verifier: str | None = None) -> SpotifyPKCE:
    """Build a ``SpotifyPKCE`` auth manager backed by an in-memory token cache.

    Args:
        code_verifier: A previously-generated PKCE code verifier to resume
            a handshake started by :func:`login`. ``None`` starts a fresh
            handshake (verifier/challenge are lazily generated on first use).

    Returns:
        SpotifyPKCE: A configured auth manager that never persists tokens
        to disk.
    """
    settings = get_settings()
    manager = SpotifyPKCE(
        client_id=settings.SPOTIFY_CLIENT_ID or "stub-client-id",
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope=_SCOPE,
        cache_handler=MemoryCacheHandler(),
    )
    if code_verifier is not None:
        manager.code_verifier = code_verifier
        # Also set code_challenge: get_access_token regenerates a fresh
        # verifier/challenge pair if EITHER is None, which would discard the
        # stored verifier and cause Spotify to reject the exchange with
        # "code_verifier was incorrect". Derived from the verifier we just set.
        manager.code_challenge = manager._get_code_challenge()
    return manager


@router.get("/login", response_model=AuthLoginResponse)
def login(db: Session = Depends(get_db)) -> AuthLoginResponse:
    """Start a Spotify PKCE authorization handshake.

    Generates a fresh ``code_verifier``/``code_challenge`` pair and a
    random CSRF ``state``, persists the ``state -> code_verifier`` mapping
    so :func:`callback` can recover it later, and returns the authorize
    URL the browser must be redirected to.

    Args:
        db: Request-scoped database session.

    Returns:
        AuthLoginResponse: The Spotify authorize URL plus the CSRF state.
    """
    manager = _build_pkce_manager()
    manager.get_pkce_handshake_parameters()
    state = secrets.token_urlsafe(16)

    db.add(
        OAuthState(
            state=state,
            code_verifier=manager.code_verifier,
            created_at=datetime.now(UTC),
        )
    )
    db.commit()

    authorize_url = manager.get_authorize_url(state=state)
    return AuthLoginResponse(authorize_url=authorize_url, state=state)


@router.get(
    "/callback",
    response_model=AuthCallbackResponse,
    responses={400: {"model": AuthError, "description": "Missing/invalid code or state."}},
)
def callback(
    code: str | None = Query(default=None, description="Authorization code returned by Spotify."),
    state: str | None = Query(default=None, description="CSRF state echoed back from /auth/login."),
    db: Session = Depends(get_db),
) -> AuthCallbackResponse:
    """Exchange an authorization ``code`` for a persisted session.

    Args:
        code: The authorization code Spotify appended to the redirect. Required.
        state: The CSRF state originally issued by ``/auth/login``. Required
            to recover the matching PKCE ``code_verifier``.
        db: Request-scoped database session.

    Returns:
        AuthCallbackResponse: The newly-minted session.

    Raises:
        HTTPException: 400 if ``code``/``state`` is missing or ``state`` is
            unknown/expired; 502 if the Spotify token exchange or profile
            fetch fails.
    """
    if not code:
        raise HTTPException(status_code=400, detail="Missing 'code' query parameter.")
    if not state:
        raise HTTPException(status_code=400, detail="Missing 'state' query parameter.")

    oauth_state = db.get(OAuthState, state)
    if oauth_state is None:
        raise HTTPException(status_code=400, detail="Unknown or expired 'state' parameter.")

    manager = _build_pkce_manager(code_verifier=oauth_state.code_verifier)
    try:
        manager.get_access_token(code=code, check_cache=False)
    except SpotifyOauthError as exc:
        logging.getLogger("app.auth").error("token exchange failed: %r", exc)
        raise HTTPException(
            status_code=502, detail=f"Spotify token exchange failed: {exc}"
        ) from exc

    token_info = manager.cache_handler.get_cached_token()
    if token_info is None:
        raise HTTPException(status_code=502, detail="Spotify token exchange returned no token.")

    access_token = token_info["access_token"]
    refresh_token = token_info.get("refresh_token")
    expires_at = datetime.fromtimestamp(token_info["expires_at"], tz=UTC)

    spotify_client = spotipy.Spotify(auth=access_token, retries=0, status_retries=0)
    try:
        profile = spotify_client.current_user()
    except spotipy.SpotifyException as exc:
        logging.getLogger("app.auth").error("profile fetch failed: %r", exc)
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch Spotify profile: {exc}"
        ) from exc

    session_id = f"sess_{secrets.token_urlsafe(24)}"
    spotify_user_id = profile["id"]
    display_name = profile.get("display_name") or spotify_user_id

    db.add(
        UserSession(
            session_id=session_id,
            spotify_user_id=spotify_user_id,
            display_name=display_name,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
    )
    db.delete(oauth_state)
    db.commit()

    return AuthCallbackResponse(
        session_id=session_id,
        spotify_user_id=spotify_user_id,
        display_name=display_name,
    )
