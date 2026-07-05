"""Tests for /auth/login and /auth/callback.

The real endpoints persist an ``OAuthState`` on login and exchange it on
callback. Outbound Spotify HTTP (token exchange + profile) is mocked with
``responses``; the DB is the in-memory SQLite wired up in ``conftest``.
"""

import responses
from fastapi.testclient import TestClient

from app.models import OAuthState

TOKEN_URL = "https://accounts.spotify.com/api/token"
ME_URL = "https://api.spotify.com/v1/me/"


def test_login_returns_authorize_url_and_state(client: TestClient) -> None:
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"authorize_url", "state"}
    assert body["authorize_url"].startswith("https://accounts.spotify.com/authorize")
    assert isinstance(body["state"], str) and body["state"]


def test_login_persists_oauth_state(client: TestClient, db_session) -> None:
    state = client.get("/auth/login").json()["state"]
    row = db_session.get(OAuthState, state)
    assert row is not None
    assert row.code_verifier


def test_login_state_is_unique_per_call(client: TestClient) -> None:
    state_1 = client.get("/auth/login").json()["state"]
    state_2 = client.get("/auth/login").json()["state"]
    assert state_1 != state_2


@responses.activate
def test_callback_with_code_returns_session(client: TestClient) -> None:
    responses.add(
        responses.POST,
        TOKEN_URL,
        json={
            "access_token": "access-token-abc",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "refresh-token-xyz",
            "scope": "user-library-read",
        },
        status=200,
    )
    responses.add(
        responses.GET,
        ME_URL,
        json={"id": "spotify-user-1", "display_name": "Ada Lovelace"},
        status=200,
    )

    state = client.get("/auth/login").json()["state"]
    resp = client.get("/auth/callback", params={"code": "abc123", "state": state})

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"session_id", "spotify_user_id", "display_name"}
    assert body["session_id"]
    assert body["spotify_user_id"] == "spotify-user-1"
    assert body["display_name"] == "Ada Lovelace"


def test_callback_missing_code_returns_400(client: TestClient) -> None:
    resp = client.get("/auth/callback")
    assert resp.status_code == 400
    body = resp.json()
    assert "detail" in body


def test_callback_unknown_state_returns_400(client: TestClient) -> None:
    resp = client.get("/auth/callback", params={"code": "abc123", "state": "never-issued"})
    assert resp.status_code == 400
    assert "detail" in resp.json()
