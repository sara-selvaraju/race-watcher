from __future__ import annotations

from sqlalchemy.orm import Session

from race_watcher.db import models as m
from race_watcher.domain.models import DomainMeeting
from race_watcher.domain.ports import RaceCardSource


def ingest_meetings(session: Session, source: RaceCardSource) -> list[m.Meeting]:
    """Upsert every meeting the card source provides."""
    return [_upsert_meeting(session, d) for d in source.load_meetings()]


def ingest_meeting(session: Session, source: RaceCardSource) -> m.Meeting:
    return _upsert_meeting(session, source.load_meeting())


def _upsert_meeting(session: Session, domain: DomainMeeting) -> m.Meeting:
    """Upsert the meeting + races + runners + form lines from a card source.

    Idempotent on (track, date) and (race.meeting_id, race.number) and (runner.race_id, runner.number).
    """

    meeting = (
        session.query(m.Meeting)
        .filter(m.Meeting.track == domain.track, m.Meeting.date == domain.date)
        .one_or_none()
    )
    if meeting is None:
        meeting = m.Meeting(
            track=domain.track,
            date=domain.date,
            going=domain.going,
            rail=domain.rail,
            timezone=domain.timezone,
            source=domain.source,
        )
        session.add(meeting)
        session.flush()
    else:
        meeting.going = domain.going
        meeting.rail = domain.rail
        meeting.timezone = domain.timezone
        meeting.source = domain.source

    for d_race in domain.races:
        race = (
            session.query(m.Race)
            .filter(m.Race.meeting_id == meeting.id, m.Race.number == d_race.number)
            .one_or_none()
        )
        if race is None:
            race = m.Race(
                meeting_id=meeting.id,
                number=d_race.number,
                name=d_race.name,
                distance_m=d_race.distance_m,
                klass=d_race.klass,
                start_time_local=d_race.start_time_local,
            )
            session.add(race)
            session.flush()
        else:
            race.name = d_race.name
            race.distance_m = d_race.distance_m
            race.klass = d_race.klass
            race.start_time_local = d_race.start_time_local

        for d_runner in d_race.runners:
            runner = (
                session.query(m.Runner)
                .filter(m.Runner.race_id == race.id, m.Runner.number == d_runner.number)
                .one_or_none()
            )
            if runner is None:
                runner = m.Runner(
                    race_id=race.id,
                    number=d_runner.number,
                    name=d_runner.name,
                    jockey=d_runner.jockey,
                    trainer=d_runner.trainer,
                    barrier=d_runner.barrier,
                    weight_kg=d_runner.weight_kg,
                    scratched=d_runner.scratched,
                    seed_price=d_runner.seed_price,
                    seed_price_source=d_runner.seed_price_source,
                    seed_prediction_rating=d_runner.seed_prediction_rating,
                    seed_prediction_rationale=d_runner.seed_prediction_rationale,
                )
                session.add(runner)
                session.flush()
            else:
                runner.name = d_runner.name
                runner.jockey = d_runner.jockey
                runner.trainer = d_runner.trainer
                runner.barrier = d_runner.barrier
                runner.weight_kg = d_runner.weight_kg
                runner.scratched = d_runner.scratched
                runner.seed_price = d_runner.seed_price
                runner.seed_price_source = d_runner.seed_price_source
                runner.seed_prediction_rating = d_runner.seed_prediction_rating
                runner.seed_prediction_rationale = d_runner.seed_prediction_rationale

            # Seed form summaries: store one row per runner with note=summary.
            existing_notes = {fl.note for fl in runner.form_lines if fl.note}
            for fl in d_runner.form_lines:
                if fl.note and fl.note in existing_notes:
                    continue
                session.add(
                    m.FormLine(
                        runner_id=runner.id,
                        line_date=fl.line_date,
                        track=fl.track,
                        distance_m=fl.distance_m,
                        going=fl.going,
                        finish_pos=fl.finish_pos,
                        margin=fl.margin,
                        weight_kg=fl.weight_kg,
                        note=fl.note,
                    )
                )

    session.commit()
    return meeting
