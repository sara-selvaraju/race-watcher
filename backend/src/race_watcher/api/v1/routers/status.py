from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from race_watcher.api.deps import SessionDep
from race_watcher.api.v1.schemas.responses import StatusOut
from race_watcher.core.config import settings
from race_watcher.db import models as m
from race_watcher.repositories import race_repo
from race_watcher.services.poller import in_race_window

router = APIRouter(prefix="/status", tags=["status"])


@router.get("", response_model=StatusOut)
def status(session: Session = SessionDep) -> StatusOut:
    last_at = session.scalars(
        select(m.PriceSnapshot.taken_at).order_by(desc(m.PriceSnapshot.taken_at)).limit(1)
    ).first()
    snap_count = session.scalar(select(func.count(m.PriceSnapshot.id))) or 0
    alert_count = session.scalar(select(func.count(m.MovementAlert.id))) or 0
    now = datetime.now(UTC)
    in_win = any(
        in_race_window(mt, now=now)
        for mt in race_repo.list_meetings_between(session, *settings.race_days)
    )
    return StatusOut(
        race_date=settings.race_date,
        race_date_end=settings.race_days[1],
        odds_source=settings.odds_source,
        race_card_source=settings.race_card_source,
        prediction_engine=settings.prediction_engine,
        last_snapshot_at=last_at,
        snapshot_count=int(snap_count),
        alert_count=int(alert_count),
        in_window=in_win,
    )
