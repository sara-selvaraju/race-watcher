from __future__ import annotations

from decimal import Decimal

from race_watcher.adapters.heuristic import HeuristicEngine
from race_watcher.domain.models import DomainFormLine, DomainRunner


def _runner(number: int, name: str, price: float | None, rating: str | None, note: str = "") -> DomainRunner:
    return DomainRunner(
        number=number,
        name=name,
        seed_price=Decimal(str(price)) if price is not None else None,
        seed_prediction_rating=rating,
        form_lines=(DomainFormLine(note=note),) if note else (),
    )


def test_predictions_sum_to_one() -> None:
    runners = [
        _runner(1, "Alpha", 2.5, "top", "Heavy track winner"),
        _runner(2, "Bravo", 5.0, "danger"),
        _runner(3, "Charlie", 21.0, "roughie"),
    ]
    preds = HeuristicEngine().predict(runners)
    total = sum(p.win_prob for p in preds if p.win_prob is not None)
    assert abs(total - Decimal("1")) < Decimal("0.01")


def test_short_priced_runner_has_highest_prob() -> None:
    runners = [
        _runner(1, "Alpha", 2.5, "top"),
        _runner(2, "Bravo", 5.0, "danger"),
        _runner(3, "Charlie", 21.0, "roughie"),
    ]
    preds = HeuristicEngine().predict(runners)
    by_num = {p.runner_id: p for p in preds}
    assert by_num[1].win_prob > by_num[2].win_prob > by_num[3].win_prob


def test_wet_track_form_boosts_score() -> None:
    no_wet = _runner(1, "Alpha", 5.0, None)
    with_wet = _runner(1, "Alpha", 5.0, None, note="Won on a heavy track at Pakenham.")
    p_no = HeuristicEngine().predict([no_wet])[0]
    p_yes = HeuristicEngine().predict([with_wet])[0]
    assert p_yes.score > p_no.score


def test_no_runners_returns_empty() -> None:
    assert HeuristicEngine().predict([]) == []


def test_scratched_runners_excluded() -> None:
    scratched = DomainRunner(number=1, name="Out", scratched=True, seed_price=Decimal("3"))
    assert HeuristicEngine().predict([scratched]) == []
