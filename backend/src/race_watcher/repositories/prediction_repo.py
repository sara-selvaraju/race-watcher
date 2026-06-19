from __future__ import annotations

from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from race_watcher.db import models as m


def insert_prediction(
    session: Session,
    *,
    runner_id: int,
    engine: str,
    score: Decimal | None,
    win_prob: Decimal | None,
    rating: str | None,
    rationale: str | None,
) -> m.Prediction:
    pred = m.Prediction(
        runner_id=runner_id,
        engine=engine,
        score=score,
        win_prob=win_prob,
        rating=rating,
        rationale=rationale,
    )
    session.add(pred)
    return pred


def latest_prediction_for_runner(
    session: Session, runner_id: int, engine: str | None = None
) -> m.Prediction | None:
    stmt = (
        select(m.Prediction)
        .where(m.Prediction.runner_id == runner_id)
        .order_by(desc(m.Prediction.created_at))
        .limit(1)
    )
    if engine:
        stmt = stmt.where(m.Prediction.engine == engine)
    return session.scalars(stmt).first()
