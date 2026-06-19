from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from race_watcher.adapters import (
    get_odds_source,
    get_prediction_engine,
    get_race_card_source,
)
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


SessionDep = Depends(db_session)
CardSourceDep = Depends(race_card_source)
OddsSourceDep = Depends(odds_source)
EngineDep = Depends(prediction_engine)
