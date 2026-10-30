"""Which races the app watches.

`watch.json` (WATCH_FILE_PATH) lists meetings by track and date, optionally narrowed to certain
race numbers, plus the race card file to load them from:

    {
      "card": "seed/flemington-carnival-2026.json",
      "watch": [
        {"track": "Flemington", "date": "2026-11-03"},
        {"track": "Flemington", "date": "2026-11-07", "races": [7, 8, 9]}
      ]
    }

Everything else (the website, odds polling, ratings, picks, notes) only sees watched races, so
cost scales with what you watch. Without a watch file, every race from RACE_DATE to
RACE_DATE_END is watched, as before.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Protocol, TypeVar

from race_watcher.core.config import settings


class _Race(Protocol):
    number: int


R = TypeVar("R", bound=_Race)


class _Meeting(Protocol[R]):
    track: str
    date: date
    races: list[R]


@dataclass(frozen=True)
class WatchEntry:
    track: str
    date: date
    # None = every race at the meeting.
    races: frozenset[int] | None = None


@dataclass(frozen=True)
class Watchlist:
    start: date
    end: date
    # None = no watch file: every meeting and race between start and end.
    entries: tuple[WatchEntry, ...] | None = None
    card: Path | None = None

    def _entry(self, meeting: _Meeting) -> WatchEntry | None:
        for e in self.entries or ():
            if e.date == meeting.date and e.track.casefold() == meeting.track.casefold():
                return e
        return None

    def watches_meeting(self, meeting: _Meeting) -> bool:
        if not self.start <= meeting.date <= self.end:
            return False
        return self.entries is None or self._entry(meeting) is not None

    def races(self, meeting: _Meeting[R]) -> list[R]:
        """The meeting's watched races, in race-number order."""
        if not self.watches_meeting(meeting):
            return []
        entry = self._entry(meeting)
        races = sorted(meeting.races, key=lambda r: r.number)
        if entry is None or entry.races is None:
            return races
        return [r for r in races if r.number in entry.races]


def _parse(data: dict, base: Path) -> Watchlist:
    entries = tuple(
        WatchEntry(
            track=str(e["track"]),
            date=date.fromisoformat(e["date"]),
            races=frozenset(int(n) for n in e["races"]) if e.get("races") else None,
        )
        for e in data.get("watch", [])
    )
    if not entries:
        raise ValueError("watch file lists no meetings under \"watch\"")
    card = data.get("card")
    card_path = None
    if card:
        card_path = Path(card)
        if not card_path.is_absolute():
            card_path = (base / card_path).resolve()
    dates = [e.date for e in entries]
    return Watchlist(start=min(dates), end=max(dates), entries=entries, card=card_path)


@lru_cache(maxsize=4)
def _read(path: Path, mtime: float) -> Watchlist:  # mtime in the key re-reads after edits
    return _parse(json.loads(path.read_text()), path.parent)


def watchlist() -> Watchlist:
    path = settings.watch_file_path
    if path.is_file():
        return _read(path, path.stat().st_mtime)
    start, end = settings.race_days
    return Watchlist(start=start, end=end)
