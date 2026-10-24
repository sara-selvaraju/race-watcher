from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from race_watcher.db import models as m


def get_for_race(session: Session, race_id: int) -> m.RaceSummary | None:
    return session.scalars(select(m.RaceSummary).where(m.RaceSummary.race_id == race_id)).first()


def upsert(session: Session, *, race_id: int, summary: str, inputs_hash: str, model: str) -> m.RaceSummary:
    row = get_for_race(session, race_id)
    if row is None:
        row = m.RaceSummary(race_id=race_id, summary=summary, inputs_hash=inputs_hash, model=model)
        session.add(row)
    else:
        row.summary = summary
        row.inputs_hash = inputs_hash
        row.model = model
        # server_default only fires on insert; bump the timestamp so the UI shows when it changed.
        row.created_at = func.now()
    session.flush()
    return row
