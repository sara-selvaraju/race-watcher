from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from race_watcher.db import models as m


def insert_alert(
    session: Session,
    *,
    runner_id: int,
    from_price: Decimal,
    to_price: Decimal,
    pct_change: Decimal,
    direction: str,
    baseline: str,
) -> m.MovementAlert:
    alert = m.MovementAlert(
        runner_id=runner_id,
        from_price=from_price,
        to_price=to_price,
        pct_change=pct_change,
        direction=direction,
        baseline=baseline,
    )
    session.add(alert)
    return alert


def recent_alert_for_runner(
    session: Session, runner_id: int, *, since_minutes: int = 15, baseline: str | None = None
) -> m.MovementAlert | None:
    cutoff = datetime.now(UTC) - timedelta(minutes=since_minutes)
    stmt = (
        select(m.MovementAlert)
        .where(m.MovementAlert.runner_id == runner_id, m.MovementAlert.created_at >= cutoff)
        .order_by(desc(m.MovementAlert.created_at))
        .limit(1)
    )
    if baseline is not None:
        stmt = stmt.where(m.MovementAlert.baseline == baseline)
    return session.scalars(stmt).first()


def list_recent_alerts(
    session: Session, *, limit: int = 50, between: tuple[date, date] | None = None
) -> list[m.MovementAlert]:
    stmt = select(m.MovementAlert)
    if between is not None:
        stmt = (
            stmt.join(m.Runner, m.MovementAlert.runner_id == m.Runner.id)
            .join(m.Race, m.Runner.race_id == m.Race.id)
            .join(m.Meeting, m.Race.meeting_id == m.Meeting.id)
            .where(m.Meeting.date >= between[0], m.Meeting.date <= between[1])
        )
    stmt = (
        stmt.order_by(desc(m.MovementAlert.created_at))
        .limit(limit)
    )
    return list(session.scalars(stmt).all())
