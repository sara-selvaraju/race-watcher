from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from openai import OpenAI

from race_watcher.core.config import settings
from race_watcher.core.logging import get_logger
from race_watcher.domain.models import DomainMeeting, DomainPrice, DomainRunner

log = get_logger("openrouter")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

SUBMIT_ODDS_PARAMS = {
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
                        "description": "Race number at the meeting (1-9).",
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
                        "description": "Bookmaker / aggregator the price came from.",
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
}

SUBMIT_ODDS_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_odds",
        "description": (
            "Submit the current decimal WIN odds you found for the runners listed. "
            "Call this EXACTLY ONCE with the consolidated results. "
            "Omit any runner you could not find a credible current public price for — do not invent prices."
        ),
        "parameters": SUBMIT_ODDS_PARAMS,
    },
}

SYSTEM_PROMPT = (
    "You are a price-research agent for a personal race-day dashboard.\n\n"
    "Goal: report the current decimal WIN odds for EVERY runner in the list provided. "
    "You will be given 9 races with their full runner lists. Aim for as close to full coverage "
    "as possible — at minimum, every runner that has a tradeable price on at least one mainstream "
    "Australian bookmaker.\n\n"
    "Method:\n"
    "- Use the web_search tool LIBERALLY. One search per race is the minimum; one search per "
    "bookmaker per race is fine if it improves coverage. Try several sources to fill gaps.\n"
    "- Prefer public odds-comparison pages and bookmaker landing pages that list WIN markets: "
    "racing.com, gobet.com.au, racenet.com.au, punters.com.au, Sportsbet, TAB, Ladbrokes, Bet365.\n"
    "- For each runner, pick the best public price you can verify; record which source you used.\n\n"
    "Strict rules:\n"
    "- Do not invent prices. If a runner is genuinely not quoted anywhere public, omit it.\n"
    "- race_number and runner_number in your output MUST match the input list EXACTLY — "
    "do not renumber, do not guess. Use the horse name as a cross-check.\n"
    "- Call submit_odds EXACTLY ONCE, at the end, with the consolidated batch.\n"
    "- Output ONLY the tool call. No prose, no explanation.\n"
    "- This is for personal use, not betting advice."
)


class OpenRouterAdapter:
    """Reaches publicly available odds via OpenRouter (any chat model + Exa web search).

    Model is configurable via `OPENROUTER_MODEL` (e.g. `anthropic/claude-sonnet-4.5`,
    `openai/gpt-4o-mini`, `google/gemini-2.5-flash`, `mistralai/mistral-large`).
    When `OPENROUTER_WEB_SEARCH=true` (default), the adapter appends `:online` to the model ID,
    which routes the request through OpenRouter's web plugin: the user prompt is rewritten into
    a search query, results are injected into the context, then the model answers. Costs an
    extra ~$0.004 per search on top of the model's own pricing.
    """

    name = "openrouter"

    def __init__(
        self,
        *,
        model: str | None = None,
        client: OpenAI | None = None,
        use_web_search: bool | None = None,
    ):
        if client is None and not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")
        self._model_base = (model or settings.openrouter_model).strip()
        self._use_web_search = (
            settings.openrouter_web_search if use_web_search is None else use_web_search
        )
        if client is None:
            default_headers: dict[str, str] = {}
            if settings.openrouter_site_url:
                default_headers["HTTP-Referer"] = settings.openrouter_site_url
            if settings.openrouter_app_name:
                default_headers["X-Title"] = settings.openrouter_app_name
            client = OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=settings.openrouter_api_key,
                default_headers=default_headers or None,
            )
        self._client = client

    @property
    def effective_model(self) -> str:
        if self._use_web_search and not self._model_base.endswith(":online"):
            return f"{self._model_base}:online"
        return self._model_base

    def fetch_prices(self, meeting: DomainMeeting) -> list[DomainPrice]:
        user_msg = (
            f"Meeting: {meeting.track} on {meeting.date.isoformat()} ({meeting.timezone}).\n\n"
            "Find the current decimal WIN odds for each runner below. "
            "Call submit_odds with the consolidated results.\n\n"
            f"{_format_runner_table(meeting)}"
        )

        try:
            resp = self._client.chat.completions.create(
                model=self.effective_model,
                max_tokens=4096,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                tools=[SUBMIT_ODDS_TOOL],
                tool_choice={"type": "function", "function": {"name": "submit_odds"}},
            )
        except Exception as exc:
            log.error("openrouter.request_failed", error=str(exc))
            return []

        usage = getattr(resp, "usage", None)
        log.info(
            "openrouter.usage",
            model=self.effective_model,
            finish_reason=getattr(resp.choices[0], "finish_reason", None),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )

        message = resp.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        submit_call = next(
            (tc for tc in tool_calls if getattr(tc.function, "name", None) == "submit_odds"),
            None,
        )
        if submit_call is None:
            log.warning(
                "openrouter.no_submit_call",
                content_preview=(getattr(message, "content", None) or "")[:200],
            )
            return []

        try:
            payload = json.loads(submit_call.function.arguments)
        except json.JSONDecodeError as exc:
            log.error("openrouter.bad_json", error=str(exc), raw=submit_call.function.arguments[:200])
            return []

        return _parse_submit_payload(payload, meeting)

    def fetch_race_top_picks(self, meeting: DomainMeeting, race) -> list[dict]:
        """Research one race and return up to 3 picks: [{rank, runner_number, runner_name, rationale}, ...]."""
        user_msg = (
            f"{_format_race_runners(meeting, race)}\n\n"
            "Identify the top 3 most-likely-to-win runners. Call submit_top_picks with the results."
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.effective_model,
                max_tokens=2048,
                temperature=0,
                messages=[
                    {"role": "system", "content": TOP_PICKS_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                tools=[SUBMIT_TOP_PICKS_TOOL],
                tool_choice={"type": "function", "function": {"name": "submit_top_picks"}},
            )
        except Exception as exc:
            log.error("openrouter.top_picks_failed", race=race.number, error=str(exc))
            return []

        log.info(
            "openrouter.top_picks_usage",
            race=race.number,
            model=self.effective_model,
            finish_reason=getattr(resp.choices[0], "finish_reason", None),
        )

        message = resp.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        call = next(
            (tc for tc in tool_calls if getattr(tc.function, "name", None) == "submit_top_picks"),
            None,
        )
        if call is None:
            log.warning("openrouter.top_picks_no_tool_call", race=race.number)
            return []

        try:
            payload = json.loads(call.function.arguments)
        except json.JSONDecodeError as exc:
            log.error("openrouter.top_picks_bad_json", race=race.number, error=str(exc))
            return []

        valid_numbers = {r.number for r in race.runners if not r.scratched}
        picks: list[dict] = []
        seen_runner_numbers: set[int] = set()
        for entry in payload.get("picks") or []:
            try:
                rank = int(entry["rank"])
                runner_number = int(entry["runner_number"])
                rationale = str(entry.get("rationale") or "").strip() or None
            except (KeyError, ValueError, TypeError):
                continue
            if rank not in (1, 2, 3):
                continue
            if runner_number not in valid_numbers:
                log.warning(
                    "openrouter.top_picks_unknown_runner",
                    race=race.number,
                    runner_number=runner_number,
                )
                continue
            if runner_number in seen_runner_numbers:
                continue
            seen_runner_numbers.add(runner_number)
            picks.append(
                {
                    "rank": rank,
                    "runner_number": runner_number,
                    "rationale": rationale,
                }
            )

        # Re-rank if model skipped a position (rank=1 missing etc.)
        picks.sort(key=lambda p: p["rank"])
        for i, p in enumerate(picks, start=1):
            p["rank"] = i
        return picks[:3]


SUBMIT_TOP_PICKS_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_top_picks",
        "description": (
            "Submit your top 3 picks for the race. Rank 1 = most likely to win, "
            "2 = next, 3 = third. Each rationale should be a brief, evidence-based note "
            "(form, course/distance fit, jockey/trainer, market support, wet-track record). "
            "Call this EXACTLY ONCE."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "picks": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "rank": {
                                "type": "integer",
                                "description": "1, 2, or 3.",
                            },
                            "runner_number": {
                                "type": "integer",
                                "description": "Saddlecloth number from the input list.",
                            },
                            "runner_name": {
                                "type": "string",
                                "description": "Horse name as it appears in the input list.",
                            },
                            "rationale": {
                                "type": "string",
                                "description": "Brief evidence-based rationale (1-2 sentences).",
                            },
                        },
                        "required": ["rank", "runner_number", "runner_name", "rationale"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["picks"],
            "additionalProperties": False,
        },
    },
}

TOP_PICKS_SYSTEM = (
    "You are a horse-racing form analyst for a personal race-day dashboard.\n\n"
    "Goal: for the SINGLE race below, identify the top 3 runners most likely to win, "
    "based on current public information.\n\n"
    "Method:\n"
    "- Use web_search to research the race. Look for previews, tipster columns, recent form, "
    "wet-track form (track is rated soft/heavy), market support.\n"
    "- Prefer reputable public sources: racing.com, punters.com.au, justhorseracing, "
    "racenet.com.au, bookmaker race previews.\n"
    "- Cross-reference at least two sources where possible.\n\n"
    "Strict rules:\n"
    "- Pick ONLY from the runners listed in the input. Use the EXACT runner_number from the list.\n"
    "- Provide a SHORT, evidence-based rationale per pick. No prose outside the tool call.\n"
    "- If you can't confidently identify 3 picks, you may return fewer (down to 1) — never invent.\n"
    "- This is for personal use, not betting advice."
)


def _format_race_runners(meeting: DomainMeeting, race) -> str:
    lines: list[str] = [
        f"Race: R{race.number} {race.name}",
        f"Distance: {race.distance_m or '?'}m  Going: {meeting.going or '?'}",
        f"Track: {meeting.track}  Date: {meeting.date.isoformat()}",
        "",
        "Runners:",
    ]
    for runner in race.runners:
        if runner.scratched:
            continue
        bits = [f"  #{runner.number} {runner.name}"]
        meta: list[str] = []
        if runner.jockey:
            meta.append(f"J: {runner.jockey}")
        if runner.trainer:
            meta.append(f"T: {runner.trainer}")
        if meta:
            bits.append(" — " + " · ".join(meta))
        if runner.seed_price:
            bits.append(f" (indic. ${runner.seed_price})")
        lines.append("".join(bits))
    return "\n".join(lines)


def _format_runner_table(meeting: DomainMeeting) -> str:
    """One line per runner, deterministic, byte-identical across refreshes."""
    lines: list[str] = []
    for race in meeting.races:
        lines.append(f"R{race.number} — {race.name} ({race.distance_m or '?'}m)")
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
            log.warning("openrouter.bad_entry", entry=entry)
            continue
        if (race_num, runner_num) not in valid_keys:
            log.warning(
                "openrouter.unknown_runner",
                race_number=race_num,
                runner_number=runner_num,
                name=entry.get("runner_name"),
            )
            continue
        if price <= 0 or price > Decimal("1000"):
            log.warning("openrouter.implausible_price", price=str(price), entry=entry)
            continue
        out.append(
            DomainPrice(
                race_number=race_num,
                runner_number=runner_num,
                price=price,
                source=str(entry.get("source") or "openrouter-web"),
                taken_at=now,
            )
        )
    return out
