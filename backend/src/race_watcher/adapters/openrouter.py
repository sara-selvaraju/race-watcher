from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from openai import OpenAI

from race_watcher.core.config import settings
from race_watcher.core.logging import get_logger
from race_watcher.domain.models import DomainMeeting, DomainPrice, DomainRunner

log = get_logger("openrouter")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Perplexity Sonar returns citations as a top-level `citations` array and embeds
# [1], [2] markers in the text. We post-process those markers into markdown links
# the frontend already knows how to render.
SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_NUMBERED_REF_RE = re.compile(r"\[(\d+)\]")

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
        research_model: str | None = None,
        client: OpenAI | None = None,
        use_web_search: bool | None = None,
    ):
        if client is None and not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")
        self._model_base = (model or settings.openrouter_model).strip()
        self._research_model_base = (research_model or settings.openrouter_research_model).strip()
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
        return self._with_web(self._model_base)

    @property
    def effective_research_model(self) -> str:
        # Perplexity Sonar models have native web search baked in — don't double up with :online.
        return self._with_web(self._research_model_base, allow_online_suffix=False)

    def _with_web(self, base: str, *, allow_online_suffix: bool = True) -> str:
        if not self._use_web_search:
            return base
        if base.startswith("perplexity/") or not allow_online_suffix:
            return base  # already web-aware natively
        if base.endswith(":online"):
            return base
        return f"{base}:online"

    @staticmethod
    def _model_supports_tools(model: str) -> bool:
        """Perplexity Sonar models don't support OpenAI-style function calling on OpenRouter."""
        return not model.startswith("perplexity/")

    def _structured_call(
        self,
        *,
        model: str,
        system: str,
        user: str,
        tool: dict,
        schema_name: str,
        schema: dict,
        max_tokens: int,
    ) -> tuple[dict | None, list[str]]:
        """Run a single structured call, branching on whether the model supports tools.

        For tool-capable models: forced `tool_choice` returns the tool args as a dict.
        For Sonar (no tools): `response_format=json_schema` returns the content as JSON text.
        Returns (payload, citations) where citations is the list of source URLs (Perplexity
        provides these; empty list for other providers).
        """
        if self._model_supports_tools(model):
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    tools=[tool],
                    tool_choice={"type": "function", "function": {"name": tool["function"]["name"]}},
                )
            except Exception as exc:
                log.error("openrouter.tool_call_failed", model=model, error=str(exc))
                return None, []
            citations = _extract_citations(resp)
            message = resp.choices[0].message
            for tc in getattr(message, "tool_calls", None) or []:
                if getattr(tc.function, "name", None) == tool["function"]["name"]:
                    try:
                        return json.loads(tc.function.arguments), citations
                    except json.JSONDecodeError as exc:
                        log.error("openrouter.bad_tool_json", error=str(exc))
                        return None, citations
            log.warning("openrouter.no_tool_call", model=model)
            return None, citations

        # No-tools path: use response_format=json_schema. Sonar supports this.
        try:
            resp = self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "schema": schema,
                    },
                },
            )
        except Exception as exc:
            log.error("openrouter.json_schema_failed", model=model, error=str(exc))
            return None, []
        citations = _extract_citations(resp)
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            log.warning("openrouter.empty_content", model=model)
            return None, citations
        # Sonar sometimes wraps JSON in code fences; strip them defensively.
        if content.startswith("```"):
            content = content.strip("`").lstrip("json").strip()
        try:
            return json.loads(content), citations
        except json.JSONDecodeError as exc:
            log.error("openrouter.bad_json_content", error=str(exc), content=content[:200])
            return None, citations

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
            "Identify the top 3 most-likely-to-win runners. "
            "Return JSON matching the submit_top_picks schema."
        )
        payload, citations = self._structured_call(
            model=self.effective_research_model,
            system=TOP_PICKS_SYSTEM,
            user=user_msg,
            tool=SUBMIT_TOP_PICKS_TOOL,
            schema_name="submit_top_picks",
            schema=SUBMIT_TOP_PICKS_TOOL["function"]["parameters"],
            max_tokens=2048,
        )
        if payload is None:
            log.warning("openrouter.top_picks_empty", race=race.number)
            return []

        log.info(
            "openrouter.top_picks_done",
            race=race.number,
            model=self.effective_research_model,
            citations=len(citations),
        )

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
            if rationale:
                rationale = _linkify_citations(rationale, citations)
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

    def fetch_race_field(self, meeting: DomainMeeting, race) -> list[dict]:
        """Research the FULL field for one race. Returns [{runner_number, runner_name, jockey?, trainer?, barrier?, scratched?}, ...]."""
        user_msg = (
            f"Track: {meeting.track}\n"
            f"Date: {meeting.date.isoformat()}\n"
            f"Race: R{race.number} {race.name}\n"
            f"Distance: {race.distance_m or '?'}m\n\n"
            "Return the complete official field for this race as JSON matching the submit_field schema."
        )
        payload, _citations = self._structured_call(
            model=self.effective_research_model,
            system=FIELD_SYSTEM,
            user=user_msg,
            tool=SUBMIT_FIELD_TOOL,
            schema_name="submit_field",
            schema=SUBMIT_FIELD_TOOL["function"]["parameters"],
            max_tokens=4096,
        )
        if payload is None:
            log.warning("openrouter.field_empty", race=race.number)
            return []

        log.info(
            "openrouter.field_done",
            race=race.number,
            model=self.effective_research_model,
        )

        runners: list[dict] = []
        seen: set[int] = set()
        for entry in payload.get("runners") or []:
            try:
                num = int(entry["runner_number"])
                name = str(entry["runner_name"]).strip()
            except (KeyError, ValueError, TypeError):
                continue
            if not (1 <= num <= 30) or not name:
                continue
            if num in seen:
                continue
            seen.add(num)
            runners.append(
                {
                    "runner_number": num,
                    "runner_name": name,
                    "jockey": (entry.get("jockey") or None) or None,
                    "trainer": (entry.get("trainer") or None) or None,
                    "barrier": int(entry["barrier"]) if entry.get("barrier") is not None else None,
                    "scratched": bool(entry.get("scratched", False)),
                }
            )
        return runners


SUBMIT_TOP_PICKS_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_top_picks",
        "description": (
            "Submit your top 3 picks for the race. Rank 1 = most likely to win, "
            "2 = next, 3 = third. Each rationale is an evidence-based note "
            "(form, course/distance fit, jockey/trainer, market support, wet-track record). "
            "Cite sources with numbered markers like [1], [2] pointing to URLs you actually "
            "visited — the dashboard turns these into clickable links automatically. "
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
                                "description": (
                                    "Evidence-based rationale (2-4 sentences). Cite sources "
                                    "inline with numbered markers like [1] or [2] referencing "
                                    "the URLs you actually visited; the dashboard will render "
                                    "them as clickable links."
                                ),
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

SUBMIT_FIELD_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_field",
        "description": (
            "Submit the complete runner list for the race. Include EVERY runner you can identify "
            "from public sources, with their saddlecloth number, name, and connections if findable. "
            "Call this EXACTLY ONCE."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "runners": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 30,
                    "items": {
                        "type": "object",
                        "properties": {
                            "runner_number": {
                                "type": "integer",
                                "description": "Saddlecloth number, 1-30.",
                            },
                            "runner_name": {
                                "type": "string",
                                "description": "Horse name as listed in the field.",
                            },
                            "jockey": {
                                "type": "string",
                                "description": "Jockey name, if known.",
                            },
                            "trainer": {
                                "type": "string",
                                "description": "Trainer name, if known.",
                            },
                            "barrier": {
                                "type": "integer",
                                "description": "Barrier draw, if known.",
                            },
                            "scratched": {
                                "type": "boolean",
                                "description": "True if the runner has been scratched.",
                            },
                        },
                        "required": ["runner_number", "runner_name"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["runners"],
            "additionalProperties": False,
        },
    },
}

FIELD_SYSTEM = (
    "You are a race-card researcher for a personal race-day dashboard.\n\n"
    "Goal: for the SINGLE race below, return the COMPLETE runner field — every horse "
    "in the official field, with saddlecloth number and name. Include jockey, trainer, "
    "and barrier when listed.\n\n"
    "PRIMARY source: racing.com. Find the official Racing.com race-card page for this race "
    "and read the full field from it. Cross-check against racingvictoria.com.au, "
    "punters.com.au, or racenet.com.au if helpful.\n\n"
    "Method:\n"
    "- Search specifically for the Racing.com page (e.g. \"racing.com Flemington <race-name>\" "
    "or \"racing.com Flemington race <N>\").\n"
    "- Read the COMPLETE runner table on the page. Australian fields typically have 8-16 "
    "runners — a result of just 3-5 is almost certainly incomplete and means you should "
    "search again.\n"
    "- Include every runner number that appears on the official card, even scratched ones.\n\n"
    "Strict rules:\n"
    "- The race details below (track, date, race name, distance) identify the SINGLE race. "
    "Do NOT mix in runners from other races on the card.\n"
    "- Use the EXACT saddlecloth number as printed in the official field — do not renumber.\n"
    "- If a runner is scratched, include it with scratched: true.\n"
    "- Do NOT invent runners. If you cannot confirm a runner from a source, omit it.\n"
    "- Output ONLY the tool call. No prose."
)


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
    "- Provide an evidence-based rationale per pick (2-4 sentences). Cite every source you "
    "reference by name with a numbered marker like [1], [2] — the dashboard converts these into "
    "clickable links automatically using the URLs you actually visited.\n"
    "- No prose outside the tool call.\n"
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


def _extract_citations(resp) -> list[str]:
    """Pull citation URLs from a chat-completion response (Perplexity Sonar surfaces them
    as a top-level `citations` array; other providers usually return nothing here)."""
    raw = getattr(resp, "citations", None)
    if raw is None:
        try:
            raw = (resp.model_dump() or {}).get("citations")
        except Exception:
            raw = None
    if not raw:
        return []
    urls: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.startswith(("http://", "https://")):
            urls.append(item)
        elif isinstance(item, dict):
            for k in ("url", "link", "href"):
                v = item.get(k)
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    urls.append(v)
                    break
    return urls


def _linkify_citations(text: str, citations: list[str]) -> str:
    """Replace [N] markers with [ⁿ](url) markdown links so the frontend renders them as
    superscript anchors. Markers without a matching citation URL pass through unchanged."""
    if not citations or not text:
        return text

    def repl(m: re.Match) -> str:
        n_str = m.group(1)
        n = int(n_str)
        if 1 <= n <= len(citations):
            url = citations[n - 1]
            return f"[{n_str.translate(SUPERSCRIPT_DIGITS)}]({url})"
        return m.group(0)

    return _NUMBERED_REF_RE.sub(repl, text)
