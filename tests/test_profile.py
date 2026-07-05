"""Tests for /profile/build and /profile."""

from fastapi.testclient import TestClient


def test_build_profile_returns_expected_shape(client: TestClient) -> None:
    resp = client.post("/profile/build", json={"session_id": "sess_1"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"profile_id", "status"}
    assert body["status"] in {"building", "ready"}


def test_get_profile_returns_expected_shape(client: TestClient) -> None:
    resp = client.get("/profile", params={"session_id": "sess_1"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"summary", "clusters", "viz"}

    summary = body["summary"]
    assert set(summary.keys()) == {"top_genres", "track_count", "eclecticness"}
    assert 0.0 <= summary["eclecticness"] <= 1.0

    for cluster in body["clusters"]:
        assert set(cluster.keys()) == {"label", "size", "descriptor"}

    for point in body["viz"]:
        assert set(point.keys()) == {"x", "y", "label"}


def test_get_profile_requires_session_id(client: TestClient) -> None:
    resp = client.get("/profile")
    assert resp.status_code == 422
