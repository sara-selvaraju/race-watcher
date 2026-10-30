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


def _normalize_name(name: str) -> str:
    """Lowercase + collapse whitespace so 'The Western Front' == 'the  western front'."""
    return " ".join(name.lower().split())


def expand_all_races(session: Session, adapter, meeting_id: int | None = None) -> dict:
    """Run field expansion for every meeting on the race date (or just `meeting_id`)."""
    if not hasattr(adapter, "fetch_race_field"):
        return {"races": 0, "added": 0, "updated": 0, "skipped": "adapter_not_supported"}

    meetings = race_repo.list_meetings_between(session, *settings.race_days, meeting_id)
    if not meetings:
        return {"races": 0, "added": 0, "updated": 0, "skipped": "no_meeting"}

    totals = {"races": 0, "added": 0, "updated": 0, "skipped_duplicates": 0}
    for meeting in meetings:
        for k, v in _expand_meeting(session, adapter, meeting).items():
            totals[k] += v
    return totals


def _expand_meeting(session: Session, adapter, meeting: m.Meeting) -> dict:
    """For each race in today's meeting, research the full field and insert any missing runners.

    Idempotent: existing runners (matched on race_id + saddlecloth number, OR by normalized
    name) are updated with newly-discovered jockey/trainer/barrier but seed-derived fields are
    untouched. Name-based dedup prevents Sonar from re-inserting the same horse under a
    different saddlecloth on a repeat refresh.
    """
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
    total_skipped_dup = 0
    for race in meeting.races:
        domain_race = _to_domain_race(race)
        runners = adapter.fetch_race_field(domain_meeting, domain_race)
        if not runners:
            log.info("expand_field.empty", race=race.number)
            continue
        existing_by_num = {r.number: r for r in race.runners}
        existing_by_name = {_normalize_name(r.name): r for r in race.runners}
        added = 0
        updated = 0
        skipped_dup = 0
        for entry in runners:
            num = entry["runner_number"]
            name_key = _normalize_name(entry["runner_name"])
            existing = existing_by_num.get(num) or existing_by_name.get(name_key)
            if existing is None:
                new_runner = m.Runner(
                    race_id=race.id,
                    number=num,
                    name=entry["runner_name"],
                    jockey=entry.get("jockey"),
                    trainer=entry.get("trainer"),
                    barrier=entry.get("barrier"),
                    scratched=entry.get("scratched", False),
                )
                session.add(new_runner)
                existing_by_num[num] = new_runner
                existing_by_name[name_key] = new_runner
                added += 1
                continue
            # If the same horse is already in the field under a different saddlecloth, do not
            # insert a duplicate row. Backfill connections instead.
            if existing.number != num:
                log.info(
                    "expand_field.dup_skipped",
                    race=race.number,
                    name=entry["runner_name"],
                    incoming_num=num,
                    existing_num=existing.number,
                )
                skipped_dup += 1
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
        total_skipped_dup += skipped_dup
        log.info(
            "expand_field.race_done",
            race=race.number,
            added=added,
            updated=updated,
            skipped_dup=skipped_dup,
        )

    session.commit()
    return {
        "races": races_done,
        "added": total_added,
        "updated": total_updated,
        "skipped_duplicates": total_skipped_dup,
    }
