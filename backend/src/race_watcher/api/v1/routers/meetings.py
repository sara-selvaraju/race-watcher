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
    RunnerOut,
)
from race_watcher.core.config import settings
from race_watcher.db import models as m
from race_watcher.repositories import prediction_repo, price_repo, race_repo

router = APIRouter(prefix="/meeting", tags=["meeting"])


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


@router.get("/today", response_model=MeetingOut)
def get_today_meeting(session: Session = SessionDep) -> MeetingOut:
    meeting = race_repo.get_meeting_by_date(session, settings.race_date)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"No meeting loaded for {settings.race_date}")
    return MeetingOut(
        id=meeting.id,
        track=meeting.track,
        date=meeting.date,
        going=meeting.going,
        rail=meeting.rail,
        timezone=meeting.timezone,
        races=[
            RaceOut(
                id=race.id,
                number=race.number,
                name=race.name,
                distance_m=race.distance_m,
                klass=race.klass,
                start_time_local=race.start_time_local,
                status=race.status,
                runners=[_runner_to_out(session, r) for r in race.runners],
            )
            for race in sorted(meeting.races, key=lambda r: r.number)
        ],
    )


@router.get("/races/{race_id}", response_model=RaceOut)
def get_race(race_id: int, session: Session = SessionDep) -> RaceOut:
    race = race_repo.get_race(session, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return RaceOut(
        id=race.id,
        number=race.number,
        name=race.name,
        distance_m=race.distance_m,
        klass=race.klass,
        start_time_local=race.start_time_local,
        status=race.status,
        runners=[_runner_to_out(session, r) for r in race.runners],
    )
