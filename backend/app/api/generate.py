"""Generation job endpoints.

Phase 0: typed STUBS only, backed by an in-process dict so
``GET /generate/{job_id}`` has something realistic to poll. Real
generation (Celery task dispatch, MusicGen inference, MP3 storage) lands
in Phase 3; this in-memory store will be replaced by Celery/DB-backed job
state at that point.
"""

import uuid
from typing import Literal, TypedDict

from fastapi import APIRouter, HTTPException

from app.schemas.generate import GenerateRequest, GenerateResponse, GenerateStatusResponse

router = APIRouter(prefix="/generate", tags=["generate"])


class _JobState(TypedDict):
    """Internal bookkeeping for a stub generation job."""

    prompt: str
    polls: int


_JOBS: dict[str, _JobState] = {}

_STEPS: tuple[str, ...] = ("Queued", "Sketching melody", "Rendering audio")


def _status_for_poll(job_id: str, polls: int) -> GenerateStatusResponse:
    """Derive a deterministic, progressing status from the poll count.

    Simulates a job moving ``pending -> running -> complete`` over
    successive polls so UI/QA can exercise polling logic without a real
    worker.

    Args:
        job_id: The job's identifier.
        polls: How many times this job has been polled (1-indexed).

    Returns:
        GenerateStatusResponse: The simulated status for this poll.
    """
    status: Literal["pending", "running", "complete", "failed"]
    if polls <= 1:
        status, progress, step, url = "pending", 0.0, _STEPS[0], None
    elif polls == 2:
        status, progress, step, url = "running", 0.35, _STEPS[1], None
    elif polls == 3:
        status, progress, step, url = "running", 0.75, _STEPS[2], None
    else:
        status, progress, step = "complete", 1.0, None
        url = f"https://static.spaghettitunes.dev/generations/{job_id}.mp3"
    return GenerateStatusResponse(
        job_id=job_id, status=status, progress=progress, step=step, url=url, error=None
    )


@router.post("", response_model=GenerateResponse, status_code=202)
def create_generation_job(payload: GenerateRequest) -> GenerateResponse:
    """Enqueue a generation job.

    Stub: registers the job in an in-memory store rather than dispatching
    a Celery task.

    Args:
        payload: Prompt, optional lyrics, and taste-conditioning options.

    Returns:
        GenerateResponse: The new job's id, with status always "pending".
    """
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    _JOBS[job_id] = {"prompt": payload.prompt, "polls": 0}
    return GenerateResponse(job_id=job_id, status="pending")


@router.get("/{job_id}", response_model=GenerateStatusResponse)
def get_generation_status(job_id: str) -> GenerateStatusResponse:
    """Poll a generation job's status.

    Stub: progresses deterministically each time a given ``job_id`` is
    polled (pending -> running -> running -> complete).

    Args:
        job_id: The job id returned by ``POST /generate``.

    Returns:
        GenerateStatusResponse: The job's current (simulated) status.

    Raises:
        HTTPException: 404 if ``job_id`` is unknown.
    """
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id '{job_id}'.")
    job["polls"] += 1
    return _status_for_poll(job_id, job["polls"])
