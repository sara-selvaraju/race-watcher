from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from race_watcher.core.config import settings
from race_watcher.core.logging import get_logger
from race_watcher.db import models as m
from race_watcher.repositories import (
    prediction_repo,
    price_repo,
    race_repo,
    summary_repo,
    top_pick_repo,
)

log = get_logger("race_summary")

# Matches the frontend: a race counts as run two minutes after its advertised start.
_JUMPED_GRACE = timedelta(minutes=2)


def _has_jumped(meeting: m.Meeting, race: m.Race, now: datetime) -> bool:
    if race.start_time_local is None:
        return False
    start = datetime.combine(meeting.date, race.start_time_local, tzinfo=ZoneInfo(meeting.timezone))
    return now > start.astimezone(UTC) + _JUMPED_GRACE


def _fmt_price(p: Decimal | None) -> str:
    return f"${Decimal(p):.2f}" if p is not None else "no price"


def pick_runners(session: Session, race: m.Race) -> list[tuple[m.Runner, str | None]]:
    """The same top 3 the dashboard shows: research picks if any, else the heuristic's top 3.

    Returns (runner, research_rationale) pairs in rank order.
    """
    by_id = {r.id: r for r in race.runners}
    research = [p for p in top_pick_repo.list_for_race(session, race.id) if p.runner_id in by_id]
    if research:
        return [(by_id[p.runner_id], p.rationale) for p in research[:3]]

    scored = []
    for r in race.runners:
        if r.scratched:
            continue
        pred = prediction_repo.latest_prediction_for_runner(session, r.id)
        scored.append((Decimal(pred.win_prob) if pred and pred.win_prob is not None else Decimal(0), r))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [(r, None) for _, r in scored[:3]]


def build_facts(session: Session, meeting: m.Meeting, race: m.Race) -> str:
    """Deterministic text block of everything the summary may draw on. Also the cache key."""
    lines = [
        f"{meeting.track}, race {race.number}: {race.name}",
        f"{race.distance_m or '?'}m, {race.klass or 'class not listed'}; track {meeting.going or 'not listed'}",
        f"Picks from: {'web research' if top_pick_repo.list_for_race(session, race.id) else 'heuristic rating'}",
        "",
    ]
    for rank, (runner, rationale) in enumerate(pick_runners(session, race), start=1):
        current = price_repo.latest_price(session, runner.id)
        opening = price_repo.open_baseline_price(session, runner.id)
        pred = prediction_repo.latest_prediction_for_runner(session, runner.id)
        form = next((fl.note for fl in runner.form_lines if fl.note), None)
        lines += [
            f"Pick {rank}: {runner.name} ({runner.number})",
            f"  jockey {runner.jockey or '?'}, trainer {runner.trainer or '?'}, barrier {runner.barrier or '?'}",
            f"  price now {_fmt_price(current.price if current else None)}, "
            + (
                f"opening {_fmt_price(opening.price)}"
                if opening
                else f"pre-race preview quote {_fmt_price(runner.seed_price)}"
            ),
            f"  form: {form or 'none recorded'}",
        ]
        if pred and pred.win_prob is not None:
            lines.append(f"  heuristic win chance {Decimal(pred.win_prob) * 100:.0f}% ({pred.rationale})")
        if rationale:
            lines.append(f"  research: {rationale}")

    others = [r for r in race.runners if not r.scratched]
    priced = sum(1 for r in others if price_repo.latest_price(session, r.id))
    lines += ["", f"Field: {len(others)} runners, {priced} with a current price."]
    scratched = [f"{r.name} ({r.number})" for r in race.runners if r.scratched]
    if scratched:
        lines.append(f"Scratched: {', '.join(scratched)}")
    return "\n".join(lines)


def summarize_all(
    session: Session,
    adapter,
    meeting_id: int | None = None,
    *,
    force: bool = False,
    now: datetime | None = None,
) -> dict:
    """Write or refresh a summary for every race yet to run. Skips races whose facts are unchanged."""
    if not hasattr(adapter, "summarize_race"):
        return {"written": 0, "unchanged": 0, "skipped": "adapter_not_supported"}

    now = now or datetime.now(UTC)
    written = unchanged = failed = 0
    for meeting in race_repo.list_meetings_by_date(session, settings.race_date, meeting_id):
        for race in meeting.races:
            if _has_jumped(meeting, race, now):
                continue
            facts = build_facts(session, meeting, race)
            digest = hashlib.sha256(facts.encode()).hexdigest()
            existing = summary_repo.get_for_race(session, race.id)
            if existing and existing.inputs_hash == digest and not force:
                unchanged += 1
                continue
            text = adapter.summarize_race(facts)
            if not text:
                failed += 1
                continue
            summary_repo.upsert(
                session,
                race_id=race.id,
                summary=text[:3000],
                inputs_hash=digest,
                model=adapter.summary_model[:80],
            )
            session.commit()
            written += 1
            log.info("race_summary.written", track=meeting.track, race=race.number)
    return {"written": written, "unchanged": unchanged, "failed": failed}
