"""Tests for the Celery app wiring (Phase 0: placeholder task only)."""


def test_celery_app_imports_with_redis_broker_config() -> None:
    from app.workers.celery_app import celery_app

    assert celery_app.conf.broker_url.startswith("redis://")
    assert celery_app.conf.result_backend.startswith("redis://")


def test_ping_task_runs_synchronously_without_a_broker() -> None:
    # Calling a Celery task object directly (not via .delay()/.apply_async())
    # executes it in-process, so no live Redis connection is needed here.
    from app.workers.celery_app import ping

    assert ping() == "pong"
