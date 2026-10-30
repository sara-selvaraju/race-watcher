from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from race_watcher.api.deps import SessionDep
from race_watcher.api.v1.schemas.responses import (
    FormLineOut,
    MeetingOut,
    PredictionOut,
    PriceOut,
    RaceOut,
    RaceSummaryOut,
    RunnerOut,
    TopPickOut,
)
from race_watcher.db import models as m
from race_watcher.repositories import (
    prediction_repo,
    price_repo,
    race_repo,
    summary_repo,
    top_pick_repo,
)
from race_watcher.services.watched import watched_meetings, watched_races

router = APIRouter(prefix="/meeting", tags=["meeting"])
meetings_router = APIRouter(prefix="/meetings", tags=["meeting"])


def _runner_to_out(session: Session, runner: m.Runner) -> RunnerOut:
    history = price_repo.last_n_prices(session, runner.id, n=20)
    current = history[0] if history else None
    pred = prediction_repo.latest_prediction_for_runner(session, runner.id)
    return RunnerOut(
        id=runner.id,
        number=runner.number,
        name=runner.name,
        jockey=runner.jockey,
        trainer=runner.trainer,
        barrier=runner.barrier,
        weight_kg=runner.weight_kg,
        silk=runner.silk,
        scratched=runner.scratched,
        seeded=runner.seed_price_source is not None or runner.seed_price is not None,
        form_lines=[
            FormLineOut(
                line_date=fl.line_date,
                track=fl.track,
                distance_m=fl.distance_m,
                going=fl.going,
                finish_pos=fl.finish_pos,
                margin=fl.margin,
                weight_kg=fl.weight_kg,
                note=fl.note,
            )
            for fl in runner.form_lines
        ],
        current_price=PriceOut(price=current.price, source=current.source, taken_at=current.taken_at)
        if current
        else None,
        preview_price=runner.seed_price,
        price_history=list(
            reversed(
                [
                    PriceOut(price=p.price, source=p.source, taken_at=p.taken_at)
                    for p in history
                ]
            )
        ),
        prediction=PredictionOut(
            engine=pred.engine,
            score=pred.score,
            win_prob=pred.win_prob,
            rating=pred.rating,
            rationale=pred.rationale,
            created_at=pred.created_at,
        )
        if pred
        else None,
    )


def _race_to_out(session: Session, race: m.Race) -> RaceOut:
    pick_rows = top_pick_repo.list_for_race(session, race.id)
    runners_by_id = {r.id: r for r in race.runners}
    picks = [
        TopPickOut(
            rank=p.rank,
            runner_id=p.runner_id,
            runner_number=runners_by_id[p.runner_id].number if p.runner_id in runners_by_id else 0,
            runner_name=runners_by_id[p.runner_id].name if p.runner_id in runners_by_id else "?",
            rationale=p.rationale,
            source=p.source,
            created_at=p.created_at,
        )
        for p in pick_rows
        if p.runner_id in runners_by_id
    ]
    return RaceOut(
        id=race.id,
        number=race.number,
        name=race.name,
        distance_m=race.distance_m,
        klass=race.klass,
        start_time_local=race.start_time_local,
        status=race.status,
        runners=[_runner_to_out(session, r) for r in race.runners],
        top_picks=picks,
        summary=RaceSummaryOut(text=s.summary, model=s.model, updated_at=s.created_at)
        if (s := summary_repo.get_for_race(session, race.id))
        else None,
    )


def _meeting_to_out(session: Session, meeting: m.Meeting) -> MeetingOut:
    return MeetingOut(
        id=meeting.id,
        track=meeting.track,
        date=meeting.date,
        going=meeting.going,
        rail=meeting.rail,
        timezone=meeting.timezone,
        races=[
            _race_to_out(session, race)
            for race in watched_races(meeting)
        ],
    )


@router.get("/today", response_model=MeetingOut)
def get_today_meeting(session: Session = SessionDep) -> MeetingOut:
    """First watched meeting. Kept for older clients — prefer /meetings."""
    meetings = watched_meetings(session)
    if not meetings:
        raise HTTPException(status_code=404, detail="No watched meeting loaded")
    meeting = meetings[0]
    return _meeting_to_out(session, meeting)


@meetings_router.get("", response_model=list[MeetingOut])
def list_meetings(session: Session = SessionDep) -> list[MeetingOut]:
    """Every watched meeting (see watch.json), ordered by date, with only its watched races."""
    return [
        _meeting_to_out(session, mt)
        for mt in watched_meetings(session)
    ]


@meetings_router.get("/today", response_model=list[MeetingOut])
def list_today_meetings(session: Session = SessionDep) -> list[MeetingOut]:
    """Alias of /meetings, kept for older clients."""
    return list_meetings(session)


@router.get("/races/{race_id}", response_model=RaceOut)
def get_race(race_id: int, session: Session = SessionDep) -> RaceOut:
    race = race_repo.get_race(session, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return _race_to_out(session, race)
