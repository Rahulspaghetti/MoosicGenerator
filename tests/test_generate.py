"""Tests for POST /generate and GET /generate/{job_id}."""

from fastapi.testclient import TestClient


def test_create_job_returns_202_pending(client: TestClient) -> None:
    resp = client.post("/generate", json={"session_id": "sess_1", "prompt": "lofi beats"})
    assert resp.status_code == 202
    body = resp.json()
    assert set(body.keys()) == {"job_id", "status"}
    assert body["status"] == "pending"
    assert body["job_id"]


def test_empty_prompt_returns_422(client: TestClient) -> None:
    resp = client.post("/generate", json={"session_id": "sess_1", "prompt": ""})
    assert resp.status_code == 422


def test_missing_prompt_returns_422(client: TestClient) -> None:
    resp = client.post("/generate", json={"session_id": "sess_1"})
    assert resp.status_code == 422


def test_poll_unknown_job_returns_404(client: TestClient) -> None:
    resp = client.get("/generate/does-not-exist")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_poll_job_progresses_to_complete(client: TestClient) -> None:
    create_resp = client.post("/generate", json={"session_id": "sess_1", "prompt": "lofi beats"})
    job_id = create_resp.json()["job_id"]

    statuses = []
    for _ in range(4):
        poll_resp = client.get(f"/generate/{job_id}")
        assert poll_resp.status_code == 200
        body = poll_resp.json()
        assert set(body.keys()) == {"job_id", "status", "progress", "step", "url", "error"}
        assert body["job_id"] == job_id
        assert body["status"] in {"pending", "running", "complete", "failed"}
        assert 0.0 <= body["progress"] <= 1.0
        statuses.append(body["status"])

    assert statuses[-1] == "complete"
    final_body = poll_resp.json()
    assert final_body["url"] is not None
    assert final_body["url"].endswith(".mp3")


def test_generate_accepts_optional_fields(client: TestClient) -> None:
    resp = client.post(
        "/generate",
        json={
            "session_id": "sess_1",
            "prompt": "late night drive synthwave",
            "lyrics": "city lights, empty streets",
            "enhance_lyrics": True,
            "reference_sample_ids": ["track_1", "track_2"],
        },
    )
    assert resp.status_code == 202
