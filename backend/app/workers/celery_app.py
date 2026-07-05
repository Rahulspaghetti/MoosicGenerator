"""Celery application wiring.

Points at Redis (via ``settings.REDIS_URL``) as both broker and result
backend. Only a trivial placeholder task exists here so the ``worker``
Docker Compose service can boot end-to-end; real generation tasks
(MusicGen inference, WAV->MP3 transcode, storage) land in Phase 3.

Run the worker locally with:
    celery -A app.workers.celery_app.celery_app worker --loglevel=info
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "spaghettitunes",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="spaghettitunes.ping")
def ping() -> str:
    """Trivial placeholder task used to verify the worker boots and can
    execute a task end-to-end.

    Returns:
        str: The literal string "pong".
    """
    return "pong"
