"""Pydantic schemas for the /auth/* endpoints."""

from pydantic import BaseModel, Field


class AuthLoginResponse(BaseModel):
    """Response for ``GET /auth/login``."""

    authorize_url: str = Field(..., description="Spotify PKCE authorize URL to redirect the user to.")
    state: str = Field(..., description="Random CSRF state the UI must echo back on callback.")


class AuthCallbackResponse(BaseModel):
    """Response for ``GET /auth/callback`` on success."""

    session_id: str = Field(..., description="Opaque session identifier for subsequent requests.")
    spotify_user_id: str = Field(..., description="The authenticated Spotify user's id.")
    display_name: str = Field(..., description="The authenticated Spotify user's display name.")


class AuthError(BaseModel):
    """Error body for ``GET /auth/callback`` failures (e.g. missing code)."""

    detail: str = Field(..., description="Human-readable error description.")
