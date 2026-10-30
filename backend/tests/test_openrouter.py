from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from race_watcher.adapters.openrouter import OpenRouterAdapter
from race_watcher.adapters.seed import SeedFileAdapter


@dataclass
class _Function:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    id: str
    type: str
    function: _Function


@dataclass
class _Message:
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[_ToolCall] = field(default_factory=list)


@dataclass
class _Choice:
    message: _Message
    finish_reason: str = "tool_calls"
    index: int = 0


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class _ChatResponse:
    choices: list[_Choice]
    usage: _Usage = field(default_factory=_Usage)


class _StubCompletions:
    def __init__(self, responses: list[_ChatResponse]):
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _ChatResponse:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _StubChat:
    def __init__(self, responses: list[_ChatResponse]):
        self.completions = _StubCompletions(responses)


class _StubOpenAI:
    def __init__(self, responses: list[_ChatResponse]):
        self.chat = _StubChat(responses)


def _make_response(payload: dict) -> _ChatResponse:
    return _ChatResponse(
        choices=[
            _Choice(
                message=_Message(
                    tool_calls=[
                        _ToolCall(
                            id="call_1",
                            type="function",
                            function=_Function(name="submit_odds", arguments=json.dumps(payload)),
                        )
                    ],
                )
            )
        ]
    )


def test_parses_submit_odds_tool_call(tiny_seed: Path) -> None:
    meeting = SeedFileAdapter(path=tiny_seed).load_meeting()
    payload = {
        "prices": [
            {"race_number": 1, "runner_number": 1, "runner_name": "Alpha", "price": 2.4, "source": "Sportsbet"},
            {"race_number": 1, "runner_number": 2, "runner_name": "Bravo", "price": 5.5, "source": "Ladbrokes"},
            {"race_number": 1, "runner_number": 77, "runner_name": "Ghost", "price": 10, "source": "X"},
            {"race_number": 1, "runner_number": 3, "runner_name": "Charlie", "price": 0, "source": "Bad"},
        ]
    }
    client = _StubOpenAI([_make_response(payload)])
    adapter = OpenRouterAdapter(
        client=client,  # type: ignore[arg-type]
        model="anthropic/claude-sonnet-4.5",
        use_web_search=True,
    )

    prices = adapter.fetch_prices(meeting)

    by_num = {(p.race_number, p.runner_number): p for p in prices}
    assert (1, 1) in by_num and by_num[(1, 1)].price == Decimal("2.4")
    assert (1, 2) in by_num and by_num[(1, 2)].source == "Ladbrokes"
    assert (1, 77) not in by_num  # unknown runner discarded
    assert (1, 3) not in by_num  # zero price discarded


def test_appends_online_suffix_for_web_search(tiny_seed: Path) -> None:
    meeting = SeedFileAdapter(path=tiny_seed).load_meeting()
    client = _StubOpenAI([_make_response({"prices": []})])
    adapter = OpenRouterAdapter(
        client=client,  # type: ignore[arg-type]
        model="openai/gpt-4o-mini",
        use_web_search=True,
    )

    adapter.fetch_prices(meeting)
    call = client.chat.completions.calls[0]
    assert call["model"] == "openai/gpt-4o-mini:online"
    assert call["tool_choice"] == {"type": "function", "function": {"name": "submit_odds"}}
    assert call["tools"][0]["function"]["name"] == "submit_odds"
    # System + user; runner table is byte-stable per meeting.
    assert call["messages"][0]["role"] == "system"
    assert "R1" in call["messages"][1]["content"]
    assert "Alpha" in call["messages"][1]["content"]


def test_no_online_suffix_when_web_search_off(tiny_seed: Path) -> None:
    meeting = SeedFileAdapter(path=tiny_seed).load_meeting()
    client = _StubOpenAI([_make_response({"prices": []})])
    adapter = OpenRouterAdapter(
        client=client,  # type: ignore[arg-type]
        model="anthropic/claude-sonnet-4.5",
        use_web_search=False,
    )
    adapter.fetch_prices(meeting)
    assert client.chat.completions.calls[0]["model"] == "anthropic/claude-sonnet-4.5"


def test_returns_empty_when_no_tool_call(tiny_seed: Path) -> None:
    meeting = SeedFileAdapter(path=tiny_seed).load_meeting()
    client = _StubOpenAI([
        _ChatResponse(
            choices=[_Choice(message=_Message(content="Sorry, I cannot."), finish_reason="stop")]
        )
    ])
    adapter = OpenRouterAdapter(
        client=client,  # type: ignore[arg-type]
        model="anthropic/claude-sonnet-4.5",
        use_web_search=False,
    )
    assert adapter.fetch_prices(meeting) == []


def test_summarize_race_uses_plain_model_without_web_search() -> None:
    stub = _StubOpenAI([_ChatResponse(choices=[_Choice(message=_Message(content="  Alpha (1) leads.  "))])])
    adapter = OpenRouterAdapter(model="openai/gpt-4o-mini", client=stub, use_web_search=True)  # type: ignore[arg-type]
    assert adapter.summarize_race("facts") == "Alpha (1) leads."
    call = stub.chat.completions.calls[0]
    assert call["model"] == "openai/gpt-4o-mini"
    assert "tools" not in call


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("TAB Fixed Odds", "TAB"), ("sportsbet.com.au", "Sportsbet"), ("Ladbrokes", "Ladbrokes"), ("Palmerbet", "Palmerbet")],
)
def test_bookmaker_names_are_normalised(raw: str, expected: str) -> None:
    from race_watcher.adapters.openrouter import _bookmaker

    assert _bookmaker(raw) == expected
