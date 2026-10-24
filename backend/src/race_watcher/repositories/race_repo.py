from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from race_watcher.db import models as m


def _meeting_query():
    return select(m.Meeting).options(
        selectinload(m.Meeting.races)
        .selectinload(m.Race.runners)
        .selectinload(m.Runner.form_lines)
    )


def list_meetings_by_date(
    session: Session, on_date: date, meeting_id: int | None = None
) -> list[m.Meeting]:
    """Every meeting on a date (a race day can span several tracks), ordered by id.

    `meeting_id` narrows to one meeting so admin actions can target a single track.
    """
    stmt = _meeting_query().where(m.Meeting.date == on_date).order_by(m.Meeting.id)
    if meeting_id is not None:
        stmt = stmt.where(m.Meeting.id == meeting_id)
    return list(session.scalars(stmt).all())


def get_meeting_by_date(session: Session, on_date: date) -> m.Meeting | None:
    meetings = list_meetings_by_date(session, on_date)
    return meetings[0] if meetings else None


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
