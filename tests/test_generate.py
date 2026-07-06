"""Tests for POST /generate, GET /generate/{job_id}, GET /generate/{job_id}/audio.

The MusicGen model is never loaded in tests — ``app.services.musicgen.generate``
is patched to return a tiny silent buffer. The **real** ffmpeg transcode runs on
that buffer (ffmpeg is on PATH), so the delivery path is exercised end to end.
BackgroundTasks execute synchronously under ``TestClient``, so a job is already
``complete``/``failed`` by the time ``POST`` returns.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.models import UserSession

SESSION_ID = "sess_gen_1"
SR = 32000


def _seed_session(db_session, session_id: str = SESSION_ID) -> None:
    db_session.add(
        UserSession(
            session_id=session_id,
            spotify_user_id="gen-user",
            display_name="Gen Tester",
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db_session.commit()


def _fake_audio(prompt: str, duration_s: int) -> tuple[np.ndarray, int]:
    # 0.25s of silence — enough for ffmpeg to make a valid MP3, tiny + fast.
    return np.zeros(SR // 4, dtype=np.float32), SR


@pytest.fixture()
def _tmp_media(tmp_path, monkeypatch):
    """Write generated MP3s into a throwaway dir, not the repo's backend/media."""
    monkeypatch.setattr("app.api.generate._generations_dir", lambda: tmp_path)
    return tmp_path


def test_empty_prompt_returns_422(client: TestClient) -> None:
    assert client.post("/generate", json={"session_id": SESSION_ID, "prompt": ""}).status_code == 422


def test_missing_prompt_returns_422(client: TestClient) -> None:
    assert client.post("/generate", json={"session_id": SESSION_ID}).status_code == 422


def test_unknown_session_returns_404(client: TestClient, _tmp_media) -> None:
    resp = client.post("/generate", json={"session_id": "sess_nope", "prompt": "lofi"})
    assert resp.status_code == 404


def test_poll_unknown_job_returns_404(client: TestClient) -> None:
    resp = client.get("/generate/does-not-exist")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_audio_unknown_job_returns_404(client: TestClient) -> None:
    assert client.get("/generate/does-not-exist/audio").status_code == 404


def test_generate_completes_and_serves_playable_mp3(client: TestClient, db_session, _tmp_media) -> None:
    _seed_session(db_session)
    with patch("app.services.musicgen.generate", side_effect=_fake_audio):
        create = client.post("/generate", json={"session_id": SESSION_ID, "prompt": "lofi beats"})
    assert create.status_code == 202
    body = create.json()
    assert body["status"] == "pending"
    job_id = body["job_id"]

    status = client.get(f"/generate/{job_id}")
    assert status.status_code == 200
    sbody = status.json()
    assert set(sbody.keys()) == {"job_id", "status", "progress", "step", "url", "error"}
    assert sbody["status"] == "complete"
    assert sbody["progress"] == 1.0
    assert sbody["url"] == f"/generate/{job_id}/audio"

    # The MP3 exists on disk and streams back as audio/mpeg with a body.
    assert (_tmp_media / f"{job_id}.mp3").exists()
    audio = client.get(f"/generate/{job_id}/audio")
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/mpeg"
    assert len(audio.content) > 0


def test_generation_failure_marks_job_failed(client: TestClient, db_session, _tmp_media) -> None:
    _seed_session(db_session)
    with patch("app.services.musicgen.generate", side_effect=RuntimeError("boom")):
        create = client.post("/generate", json={"session_id": SESSION_ID, "prompt": "lofi"})
    job_id = create.json()["job_id"]

    status = client.get(f"/generate/{job_id}").json()
    assert status["status"] == "failed"
    assert "boom" in status["error"]
    assert status["url"] is None


def test_generate_accepts_but_ignores_optional_fields(client: TestClient, db_session, _tmp_media) -> None:
    _seed_session(db_session)
    with patch("app.services.musicgen.generate", side_effect=_fake_audio):
        resp = client.post(
            "/generate",
            json={
                "session_id": SESSION_ID,
                "prompt": "late night drive synthwave",
                "lyrics": "city lights",
                "enhance_lyrics": True,
                "reference_sample_ids": ["track_1"],
            },
        )
    assert resp.status_code == 202
