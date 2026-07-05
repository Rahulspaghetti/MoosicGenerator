"""End-to-end smoke test walking the whole login -> generate flow.

``/auth/*`` and ``/library/sync`` are real in Phase 1, so their outbound
Spotify HTTP is mocked with ``responses``; ``/profile/*`` and ``/generate``
remain Phase 0 stubs.
"""

from unittest.mock import patch

import responses
from fastapi.testclient import TestClient


@responses.activate
def test_full_flow_smoke(client: TestClient) -> None:
    """Walk login -> callback -> sync (async job) -> profile -> generate -> poll."""
    responses.add(
        responses.POST,
        "https://accounts.spotify.com/api/token",
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
        "https://api.spotify.com/v1/me/",
        json={"id": "spotify-user-1", "display_name": "Ada Lovelace"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.spotify.com/v1/me/tracks",
        json={"items": [], "next": None},
        status=200,
    )

    assert client.get("/health").status_code == 200

    login_resp = client.get("/auth/login")
    assert login_resp.status_code == 200
    state = login_resp.json()["state"]

    callback_resp = client.get("/auth/callback", params={"code": "stub-code", "state": state})
    assert callback_resp.status_code == 200
    session_id = callback_resp.json()["session_id"]

    with patch("app.api.library.time.sleep"):
        sync_resp = client.post("/library/sync", json={"session_id": session_id})
    assert sync_resp.status_code == 200
    start = sync_resp.json()
    assert start["cached"] is False
    sync_status = client.get(f"/library/sync/{start['job_id']}")
    assert sync_status.status_code == 200
    assert sync_status.json()["status"] == "complete"

    build_resp = client.post("/profile/build", json={"session_id": session_id})
    assert build_resp.status_code == 200

    profile_resp = client.get("/profile", params={"session_id": session_id})
    assert profile_resp.status_code == 200

    generate_resp = client.post(
        "/generate", json={"session_id": session_id, "prompt": "chill synthwave for coding"}
    )
    assert generate_resp.status_code == 202
    job_id = generate_resp.json()["job_id"]

    status_resp = client.get(f"/generate/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["job_id"] == job_id
