from __future__ import annotations

from sqlalchemy.orm import Session

from race_watcher.core.config import settings
from race_watcher.core.logging import get_logger
from race_watcher.db import models as m
from race_watcher.domain.models import DomainMeeting, DomainRace, DomainRunner
from race_watcher.repositories import race_repo

log = get_logger("expand_field")


def _to_domain_race(race: m.Race) -> DomainRace:
    return DomainRace(
        number=race.number,
        name=race.name,
        distance_m=race.distance_m,
        klass=race.klass,
        start_time_local=race.start_time_local,
        runners=tuple(
            DomainRunner(
                number=r.number,
                name=r.name,
                jockey=r.jockey,
                trainer=r.trainer,
                barrier=r.barrier,
                weight_kg=r.weight_kg,
                scratched=r.scratched,
            )
            for r in race.runners
        ),
    )


def expand_all_races(session: Session, adapter) -> dict:
    """For each race in today's meeting, research the full field and insert any missing runners.

    Idempotent: existing runners (matched on race_id + saddlecloth number) are updated with
    newly-discovered jockey/trainer/barrier but their seed-derived fields are untouched.
    """
    if not hasattr(adapter, "fetch_race_field"):
        return {"races": 0, "added": 0, "updated": 0, "skipped": "adapter_not_supported"}

    meeting = race_repo.get_meeting_by_date(session, settings.race_date)
    if meeting is None:
        return {"races": 0, "added": 0, "updated": 0, "skipped": "no_meeting"}

    domain_meeting = DomainMeeting(
        track=meeting.track,
        date=meeting.date,
        going=meeting.going,
        rail=meeting.rail,
        timezone=meeting.timezone,
        source=meeting.source,
    )

    races_done = 0
    total_added = 0
    total_updated = 0
    for race in meeting.races:
        domain_race = _to_domain_race(race)
        runners = adapter.fetch_race_field(domain_meeting, domain_race)
        if not runners:
            log.info("expand_field.empty", race=race.number)
            continue
        existing_by_num = {r.number: r for r in race.runners}
        added = 0
        updated = 0
        for entry in runners:
            num = entry["runner_number"]
            existing = existing_by_num.get(num)
            if existing is None:
                session.add(
                    m.Runner(
                        race_id=race.id,
                        number=num,
                        name=entry["runner_name"],
                        jockey=entry.get("jockey"),
                        trainer=entry.get("trainer"),
                        barrier=entry.get("barrier"),
                        scratched=entry.get("scratched", False),
                    )
                )
                added += 1
                continue
            # Update connections only when missing on the existing row — never clobber seeded data.
            if not existing.jockey and entry.get("jockey"):
                existing.jockey = entry["jockey"]
                updated += 1
            if not existing.trainer and entry.get("trainer"):
                existing.trainer = entry["trainer"]
                updated += 1
            if existing.barrier is None and entry.get("barrier") is not None:
                existing.barrier = entry["barrier"]
                updated += 1
            if entry.get("scratched") and not existing.scratched:
                existing.scratched = True
                updated += 1
        session.flush()
        races_done += 1
        total_added += added
        total_updated += updated
        log.info("expand_field.race_done", race=race.number, added=added, updated=updated)

    session.commit()
    return {"races": races_done, "added": total_added, "updated": total_updated}
