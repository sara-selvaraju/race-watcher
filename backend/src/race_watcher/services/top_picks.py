from __future__ import annotations

from sqlalchemy.orm import Session

from race_watcher.core.config import settings
from race_watcher.core.logging import get_logger
from race_watcher.db import models as m
from race_watcher.domain.models import DomainFormLine, DomainMeeting, DomainRace, DomainRunner
from race_watcher.repositories import race_repo, top_pick_repo

log = get_logger("top_picks")


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
                seed_price=r.seed_price,
                seed_prediction_rating=r.seed_prediction_rating,
                seed_prediction_rationale=r.seed_prediction_rationale,
                form_lines=tuple(
                    DomainFormLine(
                        line_date=fl.line_date,
                        track=fl.track,
                        distance_m=fl.distance_m,
                        going=fl.going,
                        finish_pos=fl.finish_pos,
                        margin=fl.margin,
                        weight_kg=fl.weight_kg,
                        note=fl.note,
                    )
                    for fl in r.form_lines
                ),
            )
            for r in race.runners
        ),
    )


def refresh_all_races(session: Session, adapter, meeting_id: int | None = None) -> dict:
    """Research top picks for every race on the race date. Idempotent: replaces prior picks."""
    if not hasattr(adapter, "fetch_race_top_picks"):
        log.warning("top_picks.adapter_not_supported", adapter=adapter.name)
        return {"races": 0, "picks": 0, "skipped": "adapter_not_supported"}

    meetings = race_repo.list_meetings_by_date(session, settings.race_date, meeting_id)
    if not meetings:
        return {"races": 0, "picks": 0, "skipped": "no_meeting"}

    races = picks = 0
    for meeting in meetings:
        result = _refresh_meeting(session, adapter, meeting)
        races += result["races"]
        picks += result["picks"]
    return {"races": races, "picks": picks}


def _refresh_meeting(session: Session, adapter, meeting: m.Meeting) -> dict:

    domain_meeting = DomainMeeting(
        track=meeting.track,
        date=meeting.date,
        going=meeting.going,
        rail=meeting.rail,
        timezone=meeting.timezone,
        source=meeting.source,
    )

    races_done = 0
    total_picks = 0
    for race in meeting.races:
        domain_race = _to_domain_race(race)
        if not domain_race.runners:
            continue
        results = adapter.fetch_race_top_picks(domain_meeting, domain_race)
        if not results:
            log.info("top_picks.no_results", race=race.number)
            continue
        # Map runner_number → runner.id
        by_num = {r.number: r.id for r in race.runners if not r.scratched}
        picks_tuples: list[tuple[int, int, str | None]] = []
        for entry in results:
            runner_id = by_num.get(entry["runner_number"])
            if runner_id is None:
                continue
            picks_tuples.append((runner_id, entry["rank"], entry.get("rationale")))
        if picks_tuples:
            top_pick_repo.replace_for_race(session, race.id, picks_tuples, source=adapter.name)
            races_done += 1
            total_picks += len(picks_tuples)
    session.commit()
    log.info("top_picks.done", races=races_done, picks=total_picks)
    return {"races": races_done, "picks": total_picks}
