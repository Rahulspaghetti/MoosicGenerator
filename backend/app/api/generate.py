"""Generation job endpoints — real MusicGen inference + MP3 delivery.

``POST /generate`` enqueues a background job (DB-backed :class:`GenerationJob`)
and returns immediately with a ``job_id``. A background task runs MusicGen on the
GPU, transcodes the audio to MP3 on disk, and records the result.
``GET /generate/{job_id}`` polls status/progress; ``GET /generate/{job_id}/audio``
streams the finished MP3 (Range-enabled, so ``<audio>`` can seek).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db, get_session_factory
from app.models import GenerationJob, UserSession
from app.schemas.generate import GenerateRequest, GenerateResponse, GenerateStatusResponse
from app.services import audio, musicgen

router = APIRouter(prefix="/generate", tags=["generate"])


def _generations_dir() -> Path:
    """Return (creating if needed) the directory rendered MP3s are written to."""
    directory = Path(get_settings().MEDIA_ROOT) / "generations"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _run_generation(job_id: str) -> None:
    """Background worker: run MusicGen for ``job_id`` and record the result.

    Uses its own DB session (the request-scoped one is gone by the time this runs
    after the response). Records ``failed`` + ``error`` on any exception —
    including the deliberate CUDA-missing refusal — rather than crashing.
    """
    db: Session = get_session_factory()()
    try:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return

        job.status, job.step, job.progress = "running", "Warming model", 0.1
        db.commit()

        duration = get_settings().GENERATION_DURATION_S
        job.step, job.progress = "Composing", 0.4
        db.commit()
        samples, sample_rate = musicgen.generate(job.prompt, duration)

        job.step, job.progress = "Rendering audio", 0.85
        db.commit()
        out_path = _generations_dir() / f"{job_id}.mp3"
        audio.pcm_to_mp3(samples, sample_rate, out_path)

        job.audio_path = str(out_path)
        job.status, job.step, job.progress = "complete", "Done", 1.0
        db.commit()
    except Exception as exc:  # noqa: BLE001 - record failure on the job, don't crash the worker
        db.rollback()
        job = db.get(GenerationJob, job_id)
        if job is not None:
            job.status, job.error = "failed", str(exc)
            db.commit()
    finally:
        db.close()


@router.post("", response_model=GenerateResponse, status_code=202)
def create_generation_job(
    payload: GenerateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> GenerateResponse:
    """Enqueue a generation job and schedule the background worker.

    ``enhance_lyrics`` / ``lyrics`` / ``reference_sample_ids`` are accepted for
    forward-compatibility but ignored this phase (prompt-only conditioning).

    Raises:
        HTTPException: 404 if ``session_id`` does not match a known session.
    """
    if db.get(UserSession, payload.session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session_id.")

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    db.add(
        GenerationJob(
            job_id=job_id,
            session_id=payload.session_id,
            prompt=payload.prompt,
            status="pending",
        )
    )
    db.commit()

    background_tasks.add_task(_run_generation, job_id)
    return GenerateResponse(job_id=job_id, status="pending")


@router.get("/{job_id}", response_model=GenerateStatusResponse)
def get_generation_status(job_id: str, db: Session = Depends(get_db)) -> GenerateStatusResponse:
    """Poll a generation job's status/progress/result.

    Raises:
        HTTPException: 404 if ``job_id`` is unknown.
    """
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'.")
    url = f"/generate/{job_id}/audio" if job.status == "complete" else None
    return GenerateStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        step=job.step,
        url=url,
        error=job.error,
    )


@router.get("/{job_id}/audio")
def get_generation_audio(job_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Stream a completed job's rendered MP3.

    Raises:
        HTTPException: 404 if the job is unknown or its audio file is missing.
    """
    job = db.get(GenerationJob, job_id)
    if job is None or not job.audio_path:
        raise HTTPException(status_code=404, detail="No audio for this job.")
    path = Path(job.audio_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing.")
    return FileResponse(str(path), media_type="audio/mpeg", filename=f"{job_id}.mp3")
