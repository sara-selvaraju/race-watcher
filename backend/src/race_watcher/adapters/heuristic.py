from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from race_watcher.domain.models import DomainPrediction, DomainRunner

# Map tipster-consensus rating to a score boost (when present in the seed).
SEED_RATING_BOOST = {
    "best_bet": Decimal("0.35"),
    "top": Decimal("0.25"),
    "danger": Decimal("0.15"),
    "each-way": Decimal("0.10"),
    "watch": Decimal("0.05"),
    "roughie": Decimal("0.02"),
}

WET_TRACK_KEYWORDS = ("heavy", "soft", "wet", "bog")


class HeuristicEngine:
    """Explainable score blending seed-price market signal, tipster-rating boost, and a wet-track form bump.

    NOT a trained model. NOT financial advice.
    """

    name = "heuristic"

    def predict(self, race_runners: Iterable[DomainRunner]) -> list[DomainPrediction]:
        runners = [r for r in race_runners if not r.scratched]
        if not runners:
            return []

        scores: list[Decimal] = []
        rationales: list[str] = []
        for runner in runners:
            score = Decimal("0.0")
            reasons: list[str] = []

            # 1) Market signal from indicative odds: cheaper price → higher score.
            if runner.seed_price and runner.seed_price > 0:
                market = (Decimal("1") / runner.seed_price).quantize(Decimal("0.0001"))
                score += market
                reasons.append(f"market {market:.2f} (@${runner.seed_price})")

            # 2) Tipster-consensus rating boost.
            if runner.seed_prediction_rating:
                boost = SEED_RATING_BOOST.get(runner.seed_prediction_rating.lower(), Decimal("0"))
                if boost:
                    score += boost
                    reasons.append(f"tipster {runner.seed_prediction_rating} (+{boost})")

            # 3) Wet-track form bump from the form summary.
            form_note = " ".join(fl.note or "" for fl in runner.form_lines).lower()
            if any(k in form_note for k in WET_TRACK_KEYWORDS):
                score += Decimal("0.08")
                reasons.append("wet-track form (+0.08)")

            scores.append(score)
            rationales.append("; ".join(reasons) or "no signal")

        total = sum(scores)
        if total <= 0:
            # Even split fallback so the response always has probabilities.
            n = Decimal(len(runners))
            probs = [Decimal("1") / n for _ in runners]
        else:
            probs = [(s / total).quantize(Decimal("0.0001")) for s in scores]

        out: list[DomainPrediction] = []
        for runner, score, prob, rationale in zip(runners, scores, probs, rationales, strict=True):
            rating = _rating_from_prob(prob)
            out.append(
                DomainPrediction(
                    runner_id=runner.number,  # caller maps runner_number → runner_id
                    engine=self.name,
                    score=score.quantize(Decimal("0.001")),
                    win_prob=prob,
                    rating=rating,
                    rationale=rationale,
                )
            )
        return out


def _rating_from_prob(p: Decimal) -> str:
    if p >= Decimal("0.30"):
        return "top"
    if p >= Decimal("0.15"):
        return "danger"
    if p >= Decimal("0.08"):
        return "each-way"
    return "watch"
