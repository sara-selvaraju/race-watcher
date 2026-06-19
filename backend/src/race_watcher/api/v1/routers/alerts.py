from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from race_watcher.api.deps import SessionDep
from race_watcher.api.v1.schemas.responses import MovementAlertOut
from race_watcher.db import models as m
from race_watcher.repositories import alert_repo

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[MovementAlertOut])
def list_alerts(session: Session = SessionDep, limit: int = 50) -> list[MovementAlertOut]:
    out: list[MovementAlertOut] = []
    for a in alert_repo.list_recent_alerts(session, limit=limit):
        runner = session.get(m.Runner, a.runner_id)
        race = session.get(m.Race, runner.race_id) if runner else None
        out.append(
            MovementAlertOut(
                id=a.id,
                runner_id=a.runner_id,
                runner_name=runner.name if runner else "?",
                race_number=race.number if race else 0,
                from_price=a.from_price,
                to_price=a.to_price,
                pct_change=a.pct_change,
                direction=a.direction,
                baseline=a.baseline,
                created_at=a.created_at,
            )
        )
    return out
