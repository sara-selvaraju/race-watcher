"""Models chosen per agent on the admin page, and OpenRouter's list of models to choose from.

A choice is saved in the database and used from the agent's next run; the worker and API read
it each time they set up an agent. Agents without a choice use their Railway variable
(OPENROUTER_MODEL or OPENROUTER_RESEARCH_MODEL).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from race_watcher.core.logging import get_logger
from race_watcher.db import models as m

log = get_logger("agent_models")

MODELS_URL = "https://openrouter.ai/api/v1/models"
CATALOGUE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    # US dollars per million tokens.
    input_per_m: Decimal | None
    output_per_m: Decimal | None
    tools: bool


def model_choices(session: Session) -> dict[str, m.AgentModel]:
    return {row.agent: row for row in session.scalars(select(m.AgentModel))}


def model_overrides(session: Session) -> dict[str, str]:
    """Agent key -> chosen model, for get_odds_source(models=...)."""
    return {k: row.model for k, row in model_choices(session).items()}


def set_model(session: Session, agent: str, model: str | None) -> None:
    """Choose `agent`'s model, or go back to its default with None."""
    row = session.get(m.AgentModel, agent)
    if model is None:
        if row is not None:
            session.delete(row)
    elif row is None:
        session.add(m.AgentModel(agent=agent, model=model, updated_at=datetime.now(UTC)))
    else:
        row.model = model
        row.updated_at = datetime.now(UTC)
    session.commit()


_catalogue: tuple[float, dict[str, ModelInfo]] | None = None
_catalogue_lock = threading.Lock()


def _per_m(price: object) -> Decimal | None:
    try:
        return (Decimal(str(price)) * 1_000_000).normalize()
    except Exception:
        return None


def _fetch_models() -> list[dict]:
    resp = httpx.get(MODELS_URL, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]


def clear_catalogue() -> None:
    global _catalogue
    with _catalogue_lock:
        _catalogue = None


def catalogue() -> dict[str, ModelInfo] | None:
    """OpenRouter's public model list (no key needed), cached for an hour. None if unreachable."""
    global _catalogue
    with _catalogue_lock:
        if _catalogue and time.monotonic() - _catalogue[0] < CATALOGUE_TTL_SECONDS:
            return _catalogue[1]
    try:
        data = _fetch_models()
    except Exception as exc:
        log.warning("agent_models.catalogue_failed", error=str(exc))
        return _catalogue[1] if _catalogue else None
    models = {
        d["id"]: ModelInfo(
            id=d["id"],
            name=d.get("name") or d["id"],
            input_per_m=_per_m((d.get("pricing") or {}).get("prompt")),
            output_per_m=_per_m((d.get("pricing") or {}).get("completion")),
            tools="tools" in (d.get("supported_parameters") or []),
        )
        for d in data
        if isinstance(d, dict) and d.get("id")
    }
    with _catalogue_lock:
        _catalogue = (time.monotonic(), models)
    return models


def model_problem(agent_name: str, needs_tools: bool, model: str) -> str | None:
    """Why `model` can't be used for this agent, or None if it can (or the list can't be fetched)."""
    listed = catalogue()
    if listed is None:
        return None
    info = listed.get(model)
    if info is None:
        return f"OpenRouter doesn't list a model called {model!r}"
    if needs_tools and not info.tools:
        return f"{agent_name} needs a model that supports tool calling, and {model} doesn't"
    return None
