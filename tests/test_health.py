"""Tests for GET /health."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_docs_available(client: TestClient) -> None:
    resp = client.get("/docs")
    assert resp.status_code == 200
    schema_resp = client.get("/openapi.json")
    assert schema_resp.status_code == 200
    assert "paths" in schema_resp.json()
