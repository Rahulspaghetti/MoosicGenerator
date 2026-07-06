"""Tests for the library sync + durable taste profile.

``POST /library/sync`` either serves a fresh stored profile (``cached=True``)
or enqueues a background job (``cached=False`` + ``job_id``). Under
``TestClient``, BackgroundTasks run synchronously, so a job is ``complete`` by
the time ``POST`` returns and the per-user ``TasteProfile`` is written — a
follow-up sync for the same user is then served from cache. ``time.sleep`` (the
throttle + backoff) is patched so tests run instantly.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import responses
from fastapi.testclient import TestClient

from app.models import ArtistGenreCache, TasteProfile, UserSession

TRACKS_URL = "https://api.spotify.com/v1/me/tracks"
TRACKS_NEXT_URL = "https://api.spotify.com/v1/me/tracks?offset=50&limit=50"
ARTIST_URL = "https://api.spotify.com/v1/artists/{artist_id}"
PLAYLISTS_URL = "https://api.spotify.com/v1/me/playlists"

SESSION_ID = "sess_test_1"
SPOTIFY_USER = "spotify-user-1"


def _seed_session(db_session, session_id: str = SESSION_ID) -> None:
    db_session.add(
        UserSession(
            session_id=session_id,
            spotify_user_id=SPOTIFY_USER,
            display_name="Ada Lovelace",
            access_token="access-token-abc",
            refresh_token="refresh-token-xyz",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db_session.commit()


def _track(*artist_ids: str) -> dict:
    return {"track": {"artists": [{"id": a} for a in artist_ids]}}


def _page(items: list[dict], next_url: str | None = None, total: int | None = None) -> dict:
    return {"items": items, "next": next_url, "total": total if total is not None else len(items)}


def _start(client: TestClient, session_id: str = SESSION_ID, force: bool = False) -> dict:
    with patch("app.api.library.time.sleep"):
        resp = client.post("/library/sync", json={"session_id": session_id, "force": force})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"cached", "status", "job_id", "profile"}
    return body


def _run_sync(client: TestClient, session_id: str = SESSION_ID) -> dict:
    """Start a sync (expects a job), then GET the completed status."""
    start = _start(client, session_id)
    assert start["cached"] is False
    assert start["job_id"]
    status = client.get(f"/library/sync/{start['job_id']}")
    assert status.status_code == 200, status.text
    return status.json()


@responses.activate
def test_sync_completes_and_returns_expected_shape(client: TestClient, db_session) -> None:
    _seed_session(db_session)
    responses.add(responses.GET, TRACKS_URL, json=_page([], total=0), status=200)

    job = _run_sync(client)
    assert job["status"] == "complete"
    assert set(job["result"].keys()) == {"liked_count", "playlists", "genres", "synced_at"}


def test_sync_requires_session_id(client: TestClient) -> None:
    assert client.post("/library/sync", json={}).status_code == 422


def test_sync_unknown_session_returns_404(client: TestClient) -> None:
    assert client.post("/library/sync", json={"session_id": "sess_nope"}).status_code == 404


def test_status_unknown_job_returns_404(client: TestClient) -> None:
    assert client.get("/library/sync/lib_nope").status_code == 404


@responses.activate
def test_second_sync_is_served_from_cache(client: TestClient, db_session) -> None:
    """After a sync writes the profile, the next sync is cached (no new job)."""
    _seed_session(db_session)
    responses.add(responses.GET, TRACKS_URL, json=_page([_track("artist1")], total=1), status=200)
    responses.add(responses.GET, ARTIST_URL.format(artist_id="artist1"), json={"genres": ["house"]}, status=200)

    first = _run_sync(client)
    assert first["status"] == "complete"

    # Second call: fresh profile exists -> cached, no Spotify calls needed.
    second = _start(client)
    assert second["cached"] is True
    assert second["job_id"] is None
    assert second["profile"]["liked_count"] == 1
    assert "house" in second["profile"]["genres"]


@responses.activate
def test_force_bypasses_cache(client: TestClient, db_session) -> None:
    _seed_session(db_session)
    db_session.add(
        TasteProfile(
            spotify_user_id=SPOTIFY_USER,
            liked_count=99,
            genres=json.dumps(["old"]),
            playlists="[]",
            synced_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    responses.add(responses.GET, TRACKS_URL, json=_page([], total=0), status=200)

    forced = _start(client, force=True)
    assert forced["cached"] is False
    assert forced["job_id"]


def test_stale_profile_triggers_resync(client: TestClient, db_session) -> None:
    """A profile older than the TTL is not served from cache."""
    _seed_session(db_session)
    db_session.add(
        TasteProfile(
            spotify_user_id=SPOTIFY_USER,
            liked_count=5,
            genres=json.dumps(["old"]),
            playlists="[]",
            synced_at=datetime.now(UTC) - timedelta(days=365),
        )
    )
    db_session.commit()
    with responses.RequestsMock() as rsps:
        rsps.add(rsps.GET, TRACKS_URL, json=_page([], total=0), status=200)
        started = _start(client)
    assert started["cached"] is False


def test_get_profile_404_before_sync_then_returns_after(client: TestClient, db_session) -> None:
    _seed_session(db_session)
    assert client.get("/library/profile", params={"session_id": SESSION_ID}).status_code == 404

    db_session.add(
        TasteProfile(
            spotify_user_id=SPOTIFY_USER,
            liked_count=7,
            genres=json.dumps(["jazz"]),
            playlists="[]",
            synced_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    resp = client.get("/library/profile", params={"session_id": SESSION_ID})
    assert resp.status_code == 200
    assert resp.json()["liked_count"] == 7
    assert resp.json()["genres"] == ["jazz"]


@responses.activate
def test_pagination_51_tracks_follows_next(client: TestClient, db_session) -> None:
    _seed_session(db_session)
    responses.add(
        responses.GET,
        TRACKS_URL,
        json=_page([_track() for _ in range(50)], next_url=TRACKS_NEXT_URL, total=51),
        status=200,
    )
    responses.add(responses.GET, TRACKS_URL, json=_page([_track()], total=51), status=200)
    assert _run_sync(client)["result"]["liked_count"] == 51


@responses.activate
def test_backs_off_and_recovers_on_429(client: TestClient, db_session) -> None:
    _seed_session(db_session)
    responses.add(responses.GET, TRACKS_URL, json=_page([_track("artist1")], total=1), status=200)
    artist_url = ARTIST_URL.format(artist_id="artist1")
    responses.add(responses.GET, artist_url, status=429, headers={"Retry-After": "2"})
    responses.add(responses.GET, artist_url, json={"genres": ["art rock"]}, status=200)

    with patch("app.api.library.time.sleep") as mock_sleep:
        post = client.post("/library/sync", json={"session_id": SESSION_ID})
    job = client.get(f"/library/sync/{post.json()['job_id']}").json()

    assert job["status"] == "complete"
    assert "art rock" in job["result"]["genres"]
    assert mock_sleep.called


@responses.activate
def test_persistent_429_skips_artist_but_completes(client: TestClient, db_session) -> None:
    _seed_session(db_session)
    responses.add(responses.GET, TRACKS_URL, json=_page([_track("artist1")], total=1), status=200)
    responses.add(
        responses.GET, ARTIST_URL.format(artist_id="artist1"), status=429, headers={"Retry-After": "1"}
    )

    with patch("app.api.library.time.sleep"):
        post = client.post("/library/sync", json={"session_id": SESSION_ID})
    job = client.get(f"/library/sync/{post.json()['job_id']}").json()

    assert job["status"] == "complete"
    assert job["result"]["genres"] == []


@responses.activate
def test_sync_keeps_only_public_playlists(client: TestClient, db_session) -> None:
    _seed_session(db_session)
    responses.add(responses.GET, TRACKS_URL, json=_page([], total=0), status=200)
    responses.add(
        responses.GET,
        PLAYLISTS_URL,
        json=_page(
            [
                {"id": "pub1", "name": "Public Mix", "public": True, "tracks": {"total": 12}},
                {"id": "priv1", "name": "Secret", "public": False, "tracks": {"total": 3}},
                {"id": "collab1", "name": "Collab", "public": None, "tracks": {"total": 7}},
            ],
            total=3,
        ),
        status=200,
    )

    job = _run_sync(client)
    names = [p["name"] for p in job["result"]["playlists"]]
    assert names == ["Public Mix"]


@responses.activate
def test_uses_artist_genre_cache(client: TestClient, db_session) -> None:
    _seed_session(db_session)
    db_session.add(
        ArtistGenreCache(
            artist_id="artistcached",
            genres=json.dumps(["synthwave"]),
            fetched_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    responses.add(responses.GET, TRACKS_URL, json=_page([_track("artistcached")], total=1), status=200)

    job = _run_sync(client)
    assert job["status"] == "complete"
    assert job["result"]["genres"] == ["synthwave"]
    assert not any("/v1/artists/" in call.request.url for call in responses.calls)
