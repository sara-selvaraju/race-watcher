from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from race_watcher.api.deps import CardSourceDep, EngineDep, SessionDep
from race_watcher.core.config import settings
from race_watcher.domain.ports import PredictionEngine, RaceCardSource
from race_watcher.repositories import race_repo
from race_watcher.services.ingest import ingest_meeting
from race_watcher.services.predictions import run_predictions_for_race

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/ingest")
def ingest(
    session: Session = SessionDep,
    source: RaceCardSource = CardSourceDep,
) -> dict:
    meeting = ingest_meeting(session, source)
    return {"meeting_id": meeting.id, "track": meeting.track, "date": str(meeting.date)}


@router.post("/predict")
def predict(
    session: Session = SessionDep,
    engine: PredictionEngine = EngineDep,
) -> dict:
    meeting = race_repo.get_meeting_by_date(session, settings.race_date)
    if meeting is None:
        return {"created": 0, "skipped": "no_meeting"}
    created = 0
    for race in meeting.races:
        created += len(run_predictions_for_race(session, race, engine))
    session.commit()
    return {"created": created}
