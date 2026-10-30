from __future__ import annotations

import secrets
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from race_watcher.adapters import (
    get_odds_source,
    get_prediction_engine,
    get_race_card_source,
)
from race_watcher.core.config import settings
from race_watcher.db.session import SessionLocal
from race_watcher.domain.ports import OddsSource, PredictionEngine, RaceCardSource


def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def race_card_source() -> RaceCardSource:
    return get_race_card_source()


def odds_source() -> OddsSource:
    return get_odds_source()


def prediction_engine() -> PredictionEngine:
    return get_prediction_engine()


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Gate admin actions (they spend LLM credit) behind ADMIN_TOKEN when it's set."""
    expected = settings.admin_token
    if not expected:
        return
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Admin token missing or wrong")


SessionDep = Depends(db_session)
CardSourceDep = Depends(race_card_source)
OddsSourceDep = Depends(odds_source)
EngineDep = Depends(prediction_engine)
