from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from race_watcher.db import models as m
from race_watcher.domain.models import DomainFormLine, DomainRunner
from race_watcher.domain.ports import PredictionEngine
from race_watcher.repositories import prediction_repo, price_repo


def _to_domain_runner(r: m.Runner, live_price: Decimal | None = None) -> DomainRunner:
    """`live_price` (latest snapshot) takes precedence over the seed's indicative quote so the
    heuristic's market signal tracks the current market once odds have been refreshed."""
    return DomainRunner(
        number=r.number,
        name=r.name,
        jockey=r.jockey,
        trainer=r.trainer,
        barrier=r.barrier,
        weight_kg=r.weight_kg,
        scratched=r.scratched,
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
        seed_price=live_price if live_price is not None else r.seed_price,
        seed_price_source=r.seed_price_source,
        seed_prediction_rating=r.seed_prediction_rating,
        seed_prediction_rationale=r.seed_prediction_rationale,
    )


def run_predictions_for_race(
    session: Session, race: m.Race, engine: PredictionEngine
) -> list[m.Prediction]:
    """Run the prediction engine against the race's runners and persist results."""
    domain_runners = []
    for r in race.runners:
        if r.scratched:
            continue
        latest = price_repo.latest_price(session, r.id)
        domain_runners.append(_to_domain_runner(r, Decimal(latest.price) if latest else None))
    if not domain_runners:
        return []
    results = engine.predict(domain_runners)

    by_number = {r.number: r for r in race.runners}
    saved: list[m.Prediction] = []
    for pred in results:
        runner = by_number.get(pred.runner_id)  # engine.predict returns runner_number in runner_id
        if runner is None:
            continue
        saved.append(
            prediction_repo.insert_prediction(
                session,
                runner_id=runner.id,
                engine=pred.engine,
                score=pred.score,
                win_prob=pred.win_prob,
                rating=pred.rating,
                rationale=pred.rationale,
            )
        )
    session.flush()
    return saved
