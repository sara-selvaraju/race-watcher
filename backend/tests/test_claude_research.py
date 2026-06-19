from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from race_watcher.adapters.claude_research import ClaudeResearchAdapter
from race_watcher.adapters.seed import SeedFileAdapter


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class _ToolUseBlock:
    type: str
    name: str
    input: dict
    id: str = "toolu_test"


@dataclass
class _Response:
    content: list
    stop_reason: str = "tool_use"
    usage: _Usage = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = _Usage()


class _StubMessages:
    def __init__(self, responses: list[_Response]):
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _StubClient:
    def __init__(self, responses: list[_Response]):
        self.messages = _StubMessages(responses)


def test_parses_submit_odds_tool_call(tiny_seed: Path) -> None:
    meeting = SeedFileAdapter(path=tiny_seed).load_meeting()
    payload = {
        "prices": [
            {"race_number": 1, "runner_number": 1, "runner_name": "Alpha", "price": 2.4, "source": "Sportsbet"},
            {"race_number": 1, "runner_number": 2, "runner_name": "Bravo", "price": 5.5, "source": "Ladbrokes"},
            {"race_number": 1, "runner_number": 99, "runner_name": "Ghost", "price": 100, "source": "X"},
            {"race_number": 1, "runner_number": 3, "runner_name": "Charlie", "price": -1, "source": "Bad"},
        ]
    }
    client = _StubClient([
        _Response(content=[_ToolUseBlock(type="tool_use", name="submit_odds", input=payload)])
    ])
    adapter = ClaudeResearchAdapter(client=client, model="claude-sonnet-4-6")  # type: ignore[arg-type]

    prices = adapter.fetch_prices(meeting)

    nums = {(p.race_number, p.runner_number): p for p in prices}
    assert (1, 1) in nums and nums[(1, 1)].price == Decimal("2.4")
    assert (1, 2) in nums and nums[(1, 2)].source == "Ladbrokes"
    assert (1, 99) not in nums  # unknown runner discarded
    assert (1, 3) not in nums  # implausible price discarded


def test_request_uses_caching_and_correct_tools(tiny_seed: Path) -> None:
    meeting = SeedFileAdapter(path=tiny_seed).load_meeting()
    client = _StubClient([
        _Response(content=[_ToolUseBlock(type="tool_use", name="submit_odds", input={"prices": []})])
    ])
    adapter = ClaudeResearchAdapter(client=client, model="claude-sonnet-4-6")  # type: ignore[arg-type]

    adapter.fetch_prices(meeting)

    call = client.messages.calls[0]
    assert call["model"] == "claude-sonnet-4-6"
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    tool_types = [t.get("type") or t.get("name") for t in call["tools"]]
    assert "web_search_20260209" in tool_types
    assert "submit_odds" in tool_types
    # The user prompt is byte-stable per meeting (cache-friendly).
    body = call["messages"][0]["content"]
    assert "R1" in body and "Alpha" in body and meeting.track in body


def test_returns_empty_when_no_submit_call(tiny_seed: Path) -> None:
    meeting = SeedFileAdapter(path=tiny_seed).load_meeting()
    client = _StubClient([_Response(content=[], stop_reason="end_turn")])
    adapter = ClaudeResearchAdapter(client=client, model="claude-sonnet-4-6")  # type: ignore[arg-type]

    assert adapter.fetch_prices(meeting) == []
