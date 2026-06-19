from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from race_watcher.db import models as m


def list_for_race(session: Session, race_id: int) -> list[m.TopPick]:
    stmt = (
        select(m.TopPick)
        .where(m.TopPick.race_id == race_id)
        .order_by(m.TopPick.rank.asc())
    )
    return list(session.scalars(stmt).all())


def replace_for_race(
    session: Session,
    race_id: int,
    picks: list[tuple[int, int, str | None]],
    source: str = "openrouter",
) -> int:
    """Delete existing top_picks for the race and insert fresh ones.

    Each pick is (runner_id, rank, rationale).
    """
    session.execute(delete(m.TopPick).where(m.TopPick.race_id == race_id))
    for runner_id, rank, rationale in picks:
        session.add(
            m.TopPick(
                race_id=race_id,
                runner_id=runner_id,
                rank=rank,
                rationale=rationale,
                source=source,
            )
        )
    session.flush()
    return len(picks)
