from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from race_watcher.db import models as m


def insert_price(
    session: Session, *, runner_id: int, source: str, price: Decimal, taken_at: datetime
) -> m.PriceSnapshot:
    snap = m.PriceSnapshot(runner_id=runner_id, source=source, price=price, taken_at=taken_at)
    session.add(snap)
    return snap


def last_n_prices(session: Session, runner_id: int, n: int = 20) -> list[m.PriceSnapshot]:
    stmt = (
        select(m.PriceSnapshot)
        .where(m.PriceSnapshot.runner_id == runner_id)
        .order_by(desc(m.PriceSnapshot.taken_at))
        .limit(n)
    )
    return list(session.scalars(stmt).all())


def latest_price(session: Session, runner_id: int) -> m.PriceSnapshot | None:
    stmt = (
        select(m.PriceSnapshot)
        .where(m.PriceSnapshot.runner_id == runner_id)
        .order_by(desc(m.PriceSnapshot.taken_at))
        .limit(1)
    )
    return session.scalars(stmt).first()


def open_baseline_price(session: Session, runner_id: int) -> m.PriceSnapshot | None:
    """First snapshot on record for the runner — used as the 'open' baseline."""
    stmt = (
        select(m.PriceSnapshot)
        .where(m.PriceSnapshot.runner_id == runner_id)
        .order_by(m.PriceSnapshot.taken_at.asc())
        .limit(1)
    )
    return session.scalars(stmt).first()
