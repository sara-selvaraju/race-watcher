from __future__ import annotations

from pathlib import Path

from race_watcher.adapters.mock_odds import MockOddsAdapter
from race_watcher.adapters.seed import SeedFileAdapter


def test_mock_returns_prices_for_each_runner_with_seed_price(tiny_seed: Path) -> None:
    meeting = SeedFileAdapter(path=tiny_seed).load_meeting()
    prices = MockOddsAdapter(jitter_pct=0, seed=1).fetch_prices(meeting)
    assert len(prices) == 3
    nums = {(p.race_number, p.runner_number) for p in prices}
    assert nums == {(1, 1), (1, 2), (1, 3)}
    assert all(p.source == "mock" for p in prices)
