from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from race_watcher.adapters.openrouter import OpenRouterAdapter
from race_watcher.adapters.seed import SeedFileAdapter
from race_watcher.api.app import app
from race_watcher.api.deps import db_session
from race_watcher.core.config import settings
from race_watcher.db.base import Base
from race_watcher.services.admin_overview import overview
from race_watcher.services.agent_models import model_overrides, set_model
from race_watcher.services.agent_runs import model_used
from race_watcher.services.ingest import ingest_meetings


@pytest.fixture
def session(tiny_seed: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "race_date", date(2026, 6, 20))
    monkeypatch.setattr(settings, "race_date_end", None)
    monkeypatch.setattr(settings, "odds_source", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "anthropic/claude-sonnet-4.5")
    monkeypatch.setattr(settings, "openrouter_research_model", "perplexity/sonar-pro")
    monkeypatch.setattr(settings, "openrouter_web_search", True)
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


def test_adapter_uses_each_agents_model() -> None:
    adapter = OpenRouterAdapter(
        model="anthropic/claude-sonnet-4.5",
        research_model="perplexity/sonar-pro",
        client=object(),  # type: ignore[arg-type]
        use_web_search=True,
        models={"odds": "anthropic/claude-haiku-5.5", "field": "anthropic/claude-sonnet-4.5"},
    )
    assert adapter.effective_model == "anthropic/claude-haiku-5.5:online"
    assert adapter.summary_model == "anthropic/claude-sonnet-4.5"
    assert adapter.research_model_for("tipster") == "perplexity/sonar-pro"
    # A research agent on a non-Perplexity model still gets web search.
    assert adapter.research_model_for("field") == "anthropic/claude-sonnet-4.5:online"
    # Runs log the model as called.
    assert model_used(adapter, "odds") == "anthropic/claude-haiku-5.5:online"
    assert model_used(adapter, "notes") == "anthropic/claude-sonnet-4.5"
    assert model_used(object(), "odds") is None


def test_choice_shows_on_overview_and_resets(session: Session) -> None:
    set_model(session, "odds", "anthropic/claude-haiku-5.5")
    odds = next(a for a in overview(session).agents if a.key == "odds")
    assert odds.model == "anthropic/claude-haiku-5.5:online"
    assert odds.model_choice is not None
    assert odds.model_choice.default == "anthropic/claude-sonnet-4.5"
    assert odds.model_choice.changed_at is not None
    assert odds.model_choice.info is not None and odds.model_choice.info.input_per_m == 1
    # Suggestions OpenRouter doesn't list are left out.
    assert set(odds.model_choice.suggested) <= {"anthropic/claude-sonnet-4.5", "anthropic/claude-haiku-5.5"}

    set_model(session, "odds", None)
    assert model_overrides(session) == {}


def test_choose_model_endpoint(client: TestClient, session: Session) -> None:
    resp = client.put("/api/v1/admin/agents/notes/model", json={"model": "anthropic/claude-haiku-5.5"})
    assert resp.status_code == 200
    assert model_overrides(session) == {"notes": "anthropic/claude-haiku-5.5"}

    # Choosing the default goes back to it.
    resp = client.put("/api/v1/admin/agents/notes/model", json={"model": "anthropic/claude-sonnet-4.5"})
    assert resp.status_code == 200
    assert model_overrides(session) == {}


@pytest.mark.parametrize(
    ("key", "model", "status"),
    [
        ("odds", "made-up/model", 400),  # not on OpenRouter's list
        ("odds", "perplexity/sonar-pro", 400),  # the odds agent needs tool calling
        ("ratings", "anthropic/claude-haiku-5.5", 400),  # not an AI agent
        ("nope", "anthropic/claude-haiku-5.5", 404),
    ],
)
def test_choose_model_rejects(client: TestClient, key: str, model: str, status: int) -> None:
    assert client.put(f"/api/v1/admin/agents/{key}/model", json={"model": model}).status_code == status


def test_models_list_has_prices(client: TestClient) -> None:
    models = {m["id"]: m for m in client.get("/api/v1/admin/models").json()}
    assert models["anthropic/claude-sonnet-4.5"]["output_per_m"] == "15"
    assert models["perplexity/sonar-pro"]["tools"] is False
