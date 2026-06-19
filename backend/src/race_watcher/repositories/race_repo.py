from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from race_watcher.db import models as m


def get_meeting_by_date(session: Session, on_date: date) -> m.Meeting | None:
    stmt = (
        select(m.Meeting)
        .where(m.Meeting.date == on_date)
        .options(
            selectinload(m.Meeting.races)
            .selectinload(m.Race.runners)
            .selectinload(m.Runner.form_lines)
        )
    )
    return session.scalars(stmt).first()


def get_race(session: Session, race_id: int) -> m.Race | None:
    stmt = (
        select(m.Race)
        .where(m.Race.id == race_id)
        .options(selectinload(m.Race.runners).selectinload(m.Runner.form_lines))
    )
    return session.scalars(stmt).first()


def list_runners_for_race_date(session: Session, on_date: date) -> list[m.Runner]:
    stmt = (
        select(m.Runner)
        .join(m.Race, m.Runner.race_id == m.Race.id)
        .join(m.Meeting, m.Race.meeting_id == m.Meeting.id)
        .where(m.Meeting.date == on_date)
    )
    return list(session.scalars(stmt).all())
