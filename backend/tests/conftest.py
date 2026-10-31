from __future__ import annotations

import json
from pathlib import Path

import pytest

from race_watcher.core.config import settings


@pytest.fixture(autouse=True)
def _no_watch_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests use RACE_DATE settings unless they write their own watch file."""
    monkeypatch.setattr(settings, "watch_file_path", tmp_path / "no-watch.json")


FAKE_OPENROUTER_MODELS = [
    {"id": "anthropic/claude-sonnet-4.5", "name": "Claude Sonnet 4.5",
     "pricing": {"prompt": "0.000003", "completion": "0.000015"}, "supported_parameters": ["tools"]},
    {"id": "anthropic/claude-haiku-5.5", "name": "Claude Haiku 5.5",
     "pricing": {"prompt": "0.000001", "completion": "0.000005"}, "supported_parameters": ["tools"]},
    {"id": "perplexity/sonar-pro", "name": "Sonar Pro",
     "pricing": {"prompt": "0.000003", "completion": "0.000015"}, "supported_parameters": []},
]


@pytest.fixture(autouse=True)
def _no_openrouter_model_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never fetch OpenRouter's model list; they get a small fake one."""
    from race_watcher.services import agent_models

    agent_models.clear_catalogue()
    monkeypatch.setattr(agent_models, "_fetch_models", lambda: FAKE_OPENROUTER_MODELS)


@pytest.fixture
def tiny_seed(tmp_path: Path) -> Path:
    data = {
        "meeting": {
            "track": "Flemington",
            "date": "2026-06-20",
            "going": "Soft 7",
            "timezone": "Australia/Melbourne",
            "source": "test",
        },
        "races": [
            {
                "number": 1,
                "name": "Test Handicap",
                "distance_m": 1200,
                "start_time": "11:55",
                "runners": [
                    {
                        "number": 1,
                        "name": "Alpha",
                        "odds": {"price": 2.50, "source": "test", "as_of": "2026-06-17"},
                        "form_summary": "Strong wet-track form.",
                        "prediction": {"engine": "tipster", "rating": "top", "rationale": "best bet"},
                    },
                    {
                        "number": 2,
                        "name": "Bravo",
                        "odds": {"price": 5.00, "source": "test", "as_of": "2026-06-17"},
                        "form_summary": "Good dry form.",
                        "prediction": {"engine": "tipster", "rating": "danger", "rationale": "second"},
                    },
                    {
                        "number": 3,
                        "name": "Charlie",
                        "odds": {"price": 21.0, "source": "test", "as_of": "2026-06-17"},
                        "form_summary": "Outsider.",
                        "prediction": {"engine": "tipster", "rating": "roughie", "rationale": "long shot"},
                    },
                ],
            }
        ],
    }
    p = tmp_path / "seed.json"
    p.write_text(json.dumps(data))
    return p
