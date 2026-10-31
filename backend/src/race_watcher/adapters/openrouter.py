from __future__ import annotations

import json
import re
import threading
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

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
                        "description": "Race number at the meeting, as given.",
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
                        "description": "Current fixed-odds decimal WIN price, e.g. 3.40.",
                    },
                    "source": {
                        "type": "string",
                        "description": "The bookmaker: TAB, Sportsbet or Ladbrokes.",
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

# Fixed-odds win prices from ONE bookmaker per race, first that has the race in this order.
# One consistent source keeps movement alerts honest: a change of source isn't a market move.
BOOKMAKERS = ("TAB", "Sportsbet", "Ladbrokes")

SYSTEM_PROMPT = (
    "You are a price-research agent for an informational race-day dashboard.\n\n"
    "Goal: report the current FIXED-ODDS WIN price for every runner in the race provided, all "
    "from ONE bookmaker.\n\n"
    "Which bookmaker: use TAB fixed odds if TAB has a fixed-odds win market for this race. If "
    "not, use Sportsbet. If neither, use Ladbrokes. Take every runner's price from that one "
    "bookmaker; do not mix bookmakers within a race.\n\n"
    "Method:\n"
    "- Use web search to find that bookmaker's current fixed-odds win market for the race.\n"
    "- Only use the bookmaker's live market (its own site or a page that clearly shows that "
    "bookmaker's current fixed odds). Do NOT use tote/parimutuel prices, 'best price' "
    "comparisons, tips articles or preview pages.\n\n"
    "Strict rules:\n"
    "- Do not invent prices. If the bookmaker doesn't quote a runner, omit it.\n"
    "- source must be exactly the bookmaker's name: TAB, Sportsbet or Ladbrokes.\n"
    "- race_number and runner_number in your output MUST match the input list EXACTLY — "
    "do not renumber, do not guess. Use the horse name as a cross-check.\n"
    "- Call submit_odds EXACTLY ONCE, at the end.\n"
    "- Output ONLY the tool call. No prose, no explanation."
)


def _bookmaker(source: str) -> str:
    """Normalise e.g. 'TAB Fixed Odds' or 'sportsbet.com.au' to the bookmaker's name."""
    low = source.casefold()
    for name in BOOKMAKERS:
        if name.casefold() in low:
            return name
    return source.strip()[:40] or "unknown"


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
        models: Mapping[str, str] | None = None,
    ):
        if client is None and not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")
        self._model_base = (model or settings.openrouter_model).strip()
        self._research_model_base = (research_model or settings.openrouter_research_model).strip()
        # Per-agent choices from the admin page ("odds", "notes", "tipster", "field"); agents
        # without one use the model or research model above.
        self._models = {k: v.strip() for k, v in (models or {}).items() if v and v.strip()}
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
        # Sites cited by web-search answers since take_sites() was last called (for the admin page).
        self._sites: Counter[str] = Counter()
        self._sites_lock = threading.Lock()

    def _note_sites(self, urls: list[str]) -> None:
        domains = {d for d in (_domain(u) for u in urls) if d}
        if domains:
            with self._sites_lock:
                self._sites.update(domains)

    def take_sites(self) -> dict[str, int]:
        """Domains cited since the last call, with how many answers cited each. Thread-safe."""
        with self._sites_lock:
            out = dict(self._sites.most_common())
            self._sites.clear()
        return out

    @property
    def effective_model(self) -> str:
        """The odds agent's model, with web search."""
        return self._with_web(self._models.get("odds", self._model_base))

    @property
    def effective_research_model(self) -> str:
        return self.research_model_for("tipster")

    def research_model_for(self, agent: str) -> str:
        """The tipster's or field checker's model. Perplexity Sonar searches the web natively;
        any other model gets web search added, since both agents depend on it."""
        return self._with_web(self._models.get(agent, self._research_model_base))

    def _with_web(self, base: str) -> str:
        if not self._use_web_search:
            return base
        if base.startswith("perplexity/"):
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
            self._note_sites(citations)
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
        self._note_sites(citations)
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
                # Room for "thinking" models (e.g. GLM), which can spend 4k+ tokens reasoning
                # before they call submit_odds. One race's answer itself is under 1k.
                max_tokens=12000,
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

        self._note_sites(_extract_citations(resp))
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
            model=self.research_model_for("tipster"),
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
            model=self.research_model_for("tipster"),
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

    @property
    def summary_model(self) -> str:
        # No `:online` — the summary only restates facts we pass in, so web search would just
        # add cost and a route for unsourced claims.
        return self._models.get("notes", self._model_base)

    def summarize_race(self, facts: str) -> str | None:
        """Write a short plain-English note on why the picks are the picks, from `facts` only."""
        try:
            resp = self._client.chat.completions.create(
                model=self.summary_model,
                max_tokens=600,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM},
                    {"role": "user", "content": facts},
                ],
            )
        except Exception as exc:
            log.error("openrouter.summary_failed", model=self.summary_model, error=str(exc))
            return None
        text = (resp.choices[0].message.content or "").strip()
        return text or None

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
            model=self.research_model_for("field"),
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

        source_url = (payload.get("source_url") or "").strip().lower()
        if "racing.com" in source_url:
            source_host = "racing.com"
        elif "racenet.com.au" in source_url:
            source_host = "racenet.com.au"
        else:
            log.warning(
                "openrouter.field_rejected_off_allowlist",
                race=race.number,
                source_url=source_url or "(empty)",
                returned_runners=len(payload.get("runners") or []),
            )
            return []

        log.info(
            "openrouter.field_done",
            race=race.number,
            model=self.research_model_for("field"),
            source_host=source_host,
            source_url=source_url,
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
            "Submit the COMPLETE official runner list for the race as read off a SINGLE "
            "race-card page on racing.com OR racenet.com.au (prefer racing.com when both "
            "are available). The source_url MUST be the exact URL you read from. If you "
            "could not access either site for this race, return source_url as an empty "
            "string and runners as an empty list — do NOT substitute with other sites "
            "and do NOT merge runners from multiple pages. Call this EXACTLY ONCE."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source_url": {
                    "type": "string",
                    "description": (
                        "Exact URL on racing.com OR racenet.com.au where you read the "
                        "complete runner table for this race (single page, not a merge). "
                        "Empty string ONLY if you could not access either site for this race."
                    ),
                },
                "runners": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": 30,
                    "items": {
                        "type": "object",
                        "properties": {
                            "runner_number": {
                                "type": "integer",
                                "description": "Saddlecloth number as printed on racing.com.",
                            },
                            "runner_name": {
                                "type": "string",
                                "description": "Horse name as printed on racing.com.",
                            },
                            "jockey": {
                                "type": "string",
                                "description": "Jockey name from the racing.com row, if listed.",
                            },
                            "trainer": {
                                "type": "string",
                                "description": "Trainer name from the racing.com row, if listed.",
                            },
                            "barrier": {
                                "type": "integer",
                                "description": "Barrier draw from the racing.com row, if listed.",
                            },
                            "scratched": {
                                "type": "boolean",
                                "description": "True if marked scratched on racing.com.",
                            },
                        },
                        "required": ["runner_number", "runner_name"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["source_url", "runners"],
            "additionalProperties": False,
        },
    },
}

FIELD_SYSTEM = (
    "You are a race-card researcher for a personal race-day dashboard.\n\n"
    "ABSOLUTE RULE — only racing.com or racenet.com.au may be used as the source.\n"
    "- Prefer racing.com when accessible. Search "
    "\"site:racing.com <track> <race-name>\" or "
    "\"racing.com <track> race <N> <date>\".\n"
    "- If racing.com is unreachable for this race, fall back to racenet.com.au — "
    "search \"site:racenet.com.au <track> race <N> <date>\" and open the "
    "official race-card / form page.\n"
    "- Read the COMPLETE runner table (saddlecloth, name, jockey, trainer, "
    "barrier) directly from the chosen page. Use ONE page only — never merge "
    "runners from multiple pages or sites.\n"
    "- Return the exact URL you read from in the source_url field. It must be on "
    "racing.com or racenet.com.au.\n"
    "- If you cannot access EITHER site for this race, return source_url = \"\" "
    "and runners = []. Do NOT substitute with punters.com.au, "
    "justhorseracing.com.au, sportsbet, racingvictoria.com.au, or any aggregator. "
    "Those have introduced wrong / stale / invented runners in the past.\n\n"
    "Strict rules — accuracy is the only thing that matters here:\n"
    "- The race details below (track, date, race name, distance) identify the "
    "SINGLE race. Do NOT mix in runners from other races, other meetings, or "
    "earlier years.\n"
    "- Use the EXACT saddlecloth number as printed on the source page — do not "
    "renumber.\n"
    "- If a runner is scratched on the source page, include it with scratched: true.\n"
    "- jockey / trainer / barrier are OPTIONAL: only fill them when they appear in "
    "the source-page row. Omit otherwise. A blank field is correct; a guessed "
    "field is a bug.\n"
    "- Do NOT invent runners. If a horse isn't on the source page, it doesn't "
    "exist for this race.\n"
    "- Output ONLY the tool call. No prose."
)


SUMMARY_SYSTEM = (
    "You write race notes for a personal race-day dashboard.\n\n"
    "You are given the facts for ONE race: the top 3 picks in order, their prices (current and "
    "opening), form figures, connections, heuristic ratings, and any research rationale.\n\n"
    "Write 3-5 short sentences of plain English explaining why these are the picks: what each "
    "pick has going for it, what the market says (shortening or drifting), and the main risk or "
    "where the picks disagree.\n\n"
    "Rules:\n"
    "- Use ONLY the facts given. Never add form, history, or opinions that aren't in them.\n"
    "- Refer to runners as name plus saddlecloth number, e.g. Pingers (4).\n"
    "- Form is already listed most recent first. Quote it in that order.\n"
    "- Form figures are finishing positions only. Never infer the grade, track, distance or "
    "date of a past run from them.\n"
    "- Never claim a runner is under- or over-valued, or that the market is wrong. The "
    "heuristic share comes from the prices themselves.\n"
    "- If the facts are thin (few prices, no research), say so plainly in one sentence.\n"
    "- No markdown, headings, bullet points, or betting advice. Plain prose only."
)


TOP_PICKS_SYSTEM = (
    "You are a horse-racing form analyst for a personal race-day dashboard.\n\n"
    "Goal: for the SINGLE race below, identify the top 3 runners most likely to win, "
    "based on current public information.\n\n"
    "Method — start at racing.com:\n"
    "- ALWAYS open the racing.com form-guide / preview / tips page for this race first. "
    "It carries the official field, form lines, and Racing.com's own tipsters. Treat it as "
    "the anchor source.\n"
    "- Then broaden with web_search: punters.com.au, justhorseracing, racenet.com.au, "
    "Sportsbet/TAB/Bet365 race previews, tipster columns. Cross-reference at least two "
    "sources for any non-trivial claim.\n\n"
    "Strict rules — accuracy beats narrative:\n"
    "- Pick ONLY from the runners listed in the input. Use the EXACT runner_number from the list.\n"
    "- Provide an evidence-based rationale per pick (2-4 sentences). EVERY specific factual "
    "claim — a price quote, a tipster mention, a form line, a recent winning result, a "
    "specific jockey/trainer/barrier reference — MUST be followed by a numbered citation "
    "marker like [1], [2] pointing to the URL you read it on. If you cannot cite a source "
    "for a claim, do not make the claim.\n"
    "- Avoid unsourced filler such as \"<stable> places horses well here\" or vague stable "
    "form generalisations unless directly quoted from a cited source for THIS race.\n"
    "- If sources disagree on a fact (e.g. trainer/jockey), prefer racing.com and either "
    "skip the conflicting detail or note the disagreement.\n"
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
                source=_bookmaker(str(entry.get("source") or "unknown")),
                taken_at=now,
            )
        )
    return out


def _extract_citations(resp) -> list[str]:
    """Pull citation URLs from a chat-completion response. Perplexity Sonar via OpenRouter
    can surface them in several spots — top-level `citations`, `search_results`, or under
    `choices[0].message.annotations` — so we probe each and log what we found."""
    try:
        dump = resp.model_dump() if hasattr(resp, "model_dump") else None
    except Exception as exc:
        dump = None
        log.warning("openrouter.dump_failed", error=str(exc))

    candidates: list = []
    # Top-level: try attribute first, then dict.
    for key in ("citations", "search_results"):
        v = getattr(resp, key, None)
        if v is None and isinstance(dump, dict):
            v = dump.get(key)
        if v:
            candidates.extend(v if isinstance(v, list) else [v])

    # Inside the message: OpenAI-style annotations or provider-specific fields.
    if isinstance(dump, dict):
        msg = (dump.get("choices") or [{}])[0].get("message") or {}
        if isinstance(msg, dict):
            for key in ("citations", "annotations", "search_results"):
                v = msg.get(key)
                if v:
                    candidates.extend(v if isinstance(v, list) else [v])

    urls: list[str] = []
    for item in candidates:
        if isinstance(item, str) and item.startswith(("http://", "https://")):
            urls.append(item)
        elif isinstance(item, dict):
            # Common shapes: {url: ...}, {link: ...}, {href: ...},
            # or OpenAI annotation {type: "url_citation", url_citation: {url: ...}}
            inner = item.get("url_citation") if isinstance(item.get("url_citation"), dict) else item
            for k in ("url", "link", "href"):
                v = inner.get(k)
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    urls.append(v)
                    break

    if not urls and isinstance(dump, dict):
        # One-shot diagnostic: log the response shape so we can see where Perplexity put them.
        msg_keys = list((dump.get("choices") or [{}])[0].get("message", {}).keys())
        log.info(
            "openrouter.citations_missing",
            top_keys=list(dump.keys()),
            message_keys=msg_keys,
        )
    return urls


def _domain(url: str) -> str | None:
    host = urlparse(url).hostname
    return host.removeprefix("www.") if host else None


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
