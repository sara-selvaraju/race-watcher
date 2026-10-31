from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from race_watcher.adapters.openrouter import OpenRouterAdapter
from race_watcher.adapters.seed import SeedFileAdapter
from race_watcher.api.app import app
from race_watcher.api.deps import db_session
from race_watcher.core.config import settings
from race_watcher.db import models as m
from race_watcher.db.base import Base
from race_watcher.services import playground
from race_watcher.services.ingest import ingest_meetings
from tests.test_openrouter import _ChatResponse, _Choice, _Message, _make_response, _StubOpenAI


@dataclass
class _CostedUsage:
    prompt_tokens: int = 1000
    completion_tokens: int = 200
    cost: float = 0.0042


@pytest.fixture
def session(tiny_seed: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "race_date", date(2026, 6, 20))
    monkeypatch.setattr(settings, "race_date_end", None)
    monkeypatch.setattr(settings, "odds_source", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "anthropic/claude-sonnet-4.5")
    monkeypatch.setattr(settings, "admin_token", None)
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        ingest_meetings(s, SeedFileAdapter(path=tiny_seed))
        s.commit()
        yield s


@pytest.fixture
def client(session: Session):
    app.dependency_overrides[db_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _fake_openrouter(monkeypatch: pytest.MonkeyPatch, response: _ChatResponse) -> dict:
    """Make the playground's adapter answer with `response`; returns what it was built with."""
    built: dict = {}

    def fake(models=None):
        built["models"] = models
        response.usage = _CostedUsage()  # type: ignore[assignment]
        return OpenRouterAdapter(client=_StubOpenAI([response]), models=models, use_web_search=True)  # type: ignore[arg-type]

    monkeypatch.setattr(playground, "get_odds_source", fake)
    return built


def _race_id(session: Session) -> int:
    return session.scalars(select(m.Race.id)).one()


def test_odds_run_returns_prices_and_cost_and_saves_nothing(
    session: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {"prices": [{"race_number": 1, "runner_number": 1, "runner_name": "Alpha", "price": 2.6, "source": "TAB"}]}
    built = _fake_openrouter(monkeypatch, _make_response(payload))

    resp = client.post(
        "/api/v1/admin/playground",
        json={"agent": "odds", "race_id": _race_id(session), "model": "anthropic/claude-haiku-5.5"},
    )
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert built["models"]["odds"] == "anthropic/claude-haiku-5.5"
    assert out["model"] == "anthropic/claude-haiku-5.5:online"
    assert [(p["runner_name"], p["price"], p["source"]) for p in out["prices"]] == [("Alpha", "2.6", "TAB")]
    assert (out["calls"], out["prompt_tokens"], out["completion_tokens"]) == (1, 1000, 200)
    assert Decimal(out["cost_usd"]) == Decimal("0.0042")
    assert session.scalar(select(func.count()).select_from(m.PriceSnapshot)) == 0
    assert session.scalar(select(func.count()).select_from(m.AgentRun)) == 0


def test_notes_run_shows_the_facts_it_was_given(
    session: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_openrouter(
        monkeypatch, _ChatResponse(choices=[_Choice(message=_Message(content="Alpha (1) leads."), finish_reason="stop")])
    )
    out = client.post("/api/v1/admin/playground", json={"agent": "notes", "race_id": _race_id(session)}).json()
    assert out["note"]["text"] == "Alpha (1) leads."
    assert "Flemington, race 1" in out["note"]["facts"]
    assert out["note"]["current"] is None
    assert session.scalar(select(func.count()).select_from(m.RaceSummary)) == 0


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"agent": "odds", "model": "perplexity/sonar-pro"}, 400),  # no tool calling
        ({"agent": "ratings"}, 400),  # not AI
        ({"agent": "nope"}, 404),
        ({"agent": "notes", "race_id": 9999}, 404),
    ],
)
def test_playground_rejects(session: Session, client: TestClient, body: dict, status: int) -> None:
    body = {"race_id": _race_id(session), **body}
    assert client.post("/api/v1/admin/playground", json=body).status_code == status


def test_usage_adds_up_cost() -> None:
    from race_watcher.adapters.openrouter import Usage

    u = Usage()
    u.add(_CostedUsage())
    u.add(_CostedUsage(cost=0.001))
    assert (u.calls, u.prompt_tokens, u.cost) == (2, 2000, Decimal("0.0052"))
