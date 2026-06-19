from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from race_watcher.domain.models import (
    DomainFormLine,
    DomainMeeting,
    DomainRace,
    DomainRunner,
)


def _to_decimal(v: float | int | str | None) -> Decimal | None:
    if v is None:
        return None
    return Decimal(str(v))


def _parse_time(v: str | None) -> time | None:
    if not v:
        return None
    return time.fromisoformat(v if len(v) > 5 else v + ":00")


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    return date.fromisoformat(v)


class SeedFileAdapter:
    name = "seed"

    def __init__(self, path: Path):
        self.path = Path(path)

    def load_meeting(self) -> DomainMeeting:
        data = json.loads(self.path.read_text())
        m = data["meeting"]
        races: list[DomainRace] = []
        for r in data["races"]:
            runners: list[DomainRunner] = []
            for rn in r["runners"]:
                odds = rn.get("odds") or {}
                pred = rn.get("prediction") or {}
                form_summary = rn.get("form_summary")
                form_lines: tuple[DomainFormLine, ...] = (
                    (DomainFormLine(note=form_summary),) if form_summary else ()
                )
                runners.append(
                    DomainRunner(
                        number=int(rn["number"]),
                        name=rn["name"],
                        jockey=rn.get("jockey"),
                        trainer=rn.get("trainer"),
                        barrier=rn.get("barrier"),
                        weight_kg=_to_decimal(rn.get("weight_kg")),
                        scratched=bool(rn.get("scratched", False)),
                        form_lines=form_lines,
                        seed_price=_to_decimal(odds.get("price")),
                        seed_price_source=odds.get("source"),
                        seed_prediction_rating=pred.get("rating"),
                        seed_prediction_rationale=pred.get("rationale"),
                    )
                )
            races.append(
                DomainRace(
                    number=int(r["number"]),
                    name=r["name"],
                    distance_m=r.get("distance_m"),
                    klass=r.get("class"),
                    start_time_local=_parse_time(r.get("start_time")),
                    runners=tuple(runners),
                )
            )
        return DomainMeeting(
            track=m["track"],
            date=_parse_date(m["date"]) or date.today(),
            going=m.get("going"),
            rail=m.get("rail"),
            timezone=m.get("timezone", "Australia/Melbourne"),
            source=m.get("source", "seed"),
            races=tuple(races),
        )

    def __repr__(self) -> str:
        return f"SeedFileAdapter(path={self.path})"


__all__ = ["SeedFileAdapter"]
