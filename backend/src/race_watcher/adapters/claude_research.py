from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import anthropic

from race_watcher.core.config import settings
from race_watcher.core.logging import get_logger
from race_watcher.domain.models import DomainMeeting, DomainPrice, DomainRunner

log = get_logger("claude_research")

SUBMIT_ODDS_TOOL = {
    "name": "submit_odds",
    "description": (
        "Submit the current decimal WIN odds you found for the runners listed below. "
        "Call this EXACTLY ONCE after you have finished researching with web_search. "
        "Omit any runner you could not find a credible current price for — do not invent prices."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "prices": {
                "type": "array",
                "description": "One entry per runner you found a current WIN price for.",
                "items": {
                    "type": "object",
                    "properties": {
                        "race_number": {
                            "type": "integer",
                            "description": "Race number at the meeting (e.g. 1-9).",
                        },
                        "runner_number": {
                            "type": "integer",
                            "description": "Saddlecloth number of the runner.",
                        },
                        "runner_name": {
                            "type": "string",
                            "description": "Horse name exactly as it appears in the source.",
                        },
                        "price": {
                            "type": "number",
                            "description": "Current decimal WIN odds, e.g. 3.40.",
                        },
                        "source": {
                            "type": "string",
                            "description": "Bookmaker or aggregator the price came from (e.g. 'Sportsbet', 'racing.com').",
                        },
                    },
                    "required": [
                        "race_number",
                        "runner_number",
                        "runner_name",
                        "price",
                        "source",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["prices"],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = (
    "You are a price-research agent for a personal race-day dashboard.\n"
    "Goal: look up current decimal WIN odds for a known list of runners using publicly "
    "available web sources, then submit them via the submit_odds tool.\n"
    "Constraints:\n"
    "- Use the web_search tool to find prices. Prefer reputable public sources "
    "(racing.com, official bookmaker landing pages, mainstream odds aggregators).\n"
    "- Do not invent prices. If a runner's current price isn't findable from a credible "
    "public source, omit that runner entirely.\n"
    "- Call submit_odds EXACTLY ONCE, after you've done your research. Do not call it before searching.\n"
    "- The numbers in the input list (race_number, runner_number) must be carried through to your output unchanged.\n"
    "- This is for personal use, not betting advice."
)


class ClaudeResearchAdapter:
    name = "claude"

    def __init__(
        self,
        *,
        model: str | None = None,
        client: anthropic.Anthropic | None = None,
        max_iterations: int = 8,
    ):
        if client is None and not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = model or settings.claude_research_model
        self._max_iterations = max_iterations

    def fetch_prices(self, meeting: DomainMeeting) -> list[DomainPrice]:
        runner_lines = _format_runner_table(meeting)
        user_msg = (
            f"Meeting: {meeting.track} on {meeting.date.isoformat()} ({meeting.timezone}).\n\n"
            "Find the current decimal WIN odds for each runner below. "
            "Use web_search, then call submit_odds once with the consolidated results.\n\n"
            f"{runner_lines}"
        )
        messages: list[dict] = [{"role": "user", "content": user_msg}]
        tools = [
            {"type": "web_search_20260209", "name": "web_search"},
            SUBMIT_ODDS_TOOL,
        ]

        for iteration in range(self._max_iterations):
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                # Cache the system prompt + tools prefix. The user message is identical across
                # refreshes for the same meeting, so it stays in the prefix-match too.
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=tools,
                messages=messages,
            )
            log.info(
                "claude.usage",
                iteration=iteration,
                stop_reason=resp.stop_reason,
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                cache_read=getattr(resp.usage, "cache_read_input_tokens", 0),
                cache_create=getattr(resp.usage, "cache_creation_input_tokens", 0),
            )

            submit_call = next(
                (b for b in resp.content if b.type == "tool_use" and b.name == "submit_odds"),
                None,
            )
            if submit_call is not None:
                return _parse_submit_payload(submit_call.input, meeting)

            if resp.stop_reason == "pause_turn":
                # Server-side web_search loop hit its internal cap; re-send to resume.
                messages.append({"role": "assistant", "content": resp.content})
                continue

            if resp.stop_reason == "end_turn":
                log.warning("claude.no_submit_call_made")
                return []

            log.warning("claude.unexpected_stop", stop_reason=resp.stop_reason)
            return []

        log.warning("claude.max_iterations_reached")
        return []


def _format_runner_table(meeting: DomainMeeting) -> str:
    """One line per runner, deterministic, byte-identical across refreshes — cache-friendly."""
    lines: list[str] = []
    for race in meeting.races:
        header = f"R{race.number} — {race.name} ({race.distance_m or '?'}m)"
        lines.append(header)
        for runner in race.runners:
            if runner.scratched:
                continue
            lines.append(f"  #{runner.number} {runner.name}{_jockey_suffix(runner)}")
    return "\n".join(lines)


def _jockey_suffix(runner: DomainRunner) -> str:
    bits = []
    if runner.jockey:
        bits.append(runner.jockey)
    if runner.trainer:
        bits.append(f"({runner.trainer})")
    return f" — {' '.join(bits)}" if bits else ""


def _parse_submit_payload(payload: dict, meeting: DomainMeeting) -> list[DomainPrice]:
    valid_keys = {(r.number, rn.number) for r in meeting.races for rn in r.runners}
    now = datetime.now(UTC)
    out: list[DomainPrice] = []
    for entry in payload.get("prices") or []:
        try:
            race_num = int(entry["race_number"])
            runner_num = int(entry["runner_number"])
            price = Decimal(str(entry["price"]))
        except (KeyError, ValueError, InvalidOperation, TypeError):
            log.warning("claude.bad_entry", entry=entry)
            continue
        if (race_num, runner_num) not in valid_keys:
            log.warning(
                "claude.unknown_runner",
                race_number=race_num,
                runner_number=runner_num,
                name=entry.get("runner_name"),
            )
            continue
        if price <= 0 or price > Decimal("1000"):
            log.warning("claude.implausible_price", price=str(price), entry=entry)
            continue
        out.append(
            DomainPrice(
                race_number=race_num,
                runner_number=runner_num,
                price=price,
                source=str(entry.get("source") or "claude-web"),
                taken_at=now,
            )
        )
    return out
