from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from race_watcher.api.app import app
from race_watcher.core.config import settings

client = TestClient(app)


@pytest.fixture
def token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "admin_token", "s3cret")
    return "s3cret"


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong"}])
def test_admin_rejects_missing_or_wrong_token(token: str, headers: dict) -> None:
    resp = client.post("/api/v1/admin/predict", headers=headers)
    assert resp.status_code == 401


def test_public_reads_need_no_token(token: str) -> None:
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
