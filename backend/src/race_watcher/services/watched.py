from __future__ import annotations

from sqlalchemy.orm import Session

from race_watcher.core.watchlist import watchlist
from race_watcher.db import models as m
from race_watcher.repositories import race_repo


def watched_meetings(session: Session, meeting_id: int | None = None) -> list[m.Meeting]:
    """Meetings on the watchlist (or just `meeting_id`, if it's watched), ordered by date.

    Loop over `watched_races(meeting)`, not `meeting.races`, to skip races that aren't watched.
    """
    wl = watchlist()
    meetings = race_repo.list_meetings_between(session, wl.start, wl.end, meeting_id)
    return [mt for mt in meetings if wl.watches_meeting(mt)]


def watched_races(meeting: m.Meeting) -> list[m.Race]:
    return watchlist().races(meeting)
