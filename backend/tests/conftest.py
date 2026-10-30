from __future__ import annotations

import json
from pathlib import Path

import pytest

from race_watcher.core.config import settings


@pytest.fixture(autouse=True)
def _no_watch_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests use RACE_DATE settings unless they write their own watch file."""
    monkeypatch.setattr(settings, "watch_file_path", tmp_path / "no-watch.json")


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
