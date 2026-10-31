from __future__ import annotations

from collections.abc import Mapping

from race_watcher.core.config import settings
from race_watcher.domain.ports import OddsSource, PredictionEngine, RaceCardSource


def get_race_card_source() -> RaceCardSource:
    if settings.race_card_source == "seed":
        from race_watcher.adapters.seed import SeedFileAdapter
        from race_watcher.core.watchlist import watchlist

        return SeedFileAdapter(path=watchlist().card or settings.seed_file_path)
    raise NotImplementedError(f"race_card_source={settings.race_card_source} not wired")


def get_odds_source(models: Mapping[str, str] | None = None) -> OddsSource:
    """`models`: per-agent model choices from the admin page (only the OpenRouter adapter uses them)."""
    if settings.odds_source == "betfair":
        from race_watcher.adapters.betfair import BetfairAdapter

        return BetfairAdapter()
    if settings.odds_source == "mock":
        from race_watcher.adapters.mock_odds import MockOddsAdapter

        return MockOddsAdapter()
    if settings.odds_source == "claude":
        from race_watcher.adapters.claude_research import ClaudeResearchAdapter

        return ClaudeResearchAdapter()
    if settings.odds_source == "openrouter":
        from race_watcher.adapters.openrouter import OpenRouterAdapter

        return OpenRouterAdapter(models=models)
    raise NotImplementedError(f"odds_source={settings.odds_source} not wired")


def get_prediction_engine() -> PredictionEngine:
    if settings.prediction_engine == "heuristic":
        from race_watcher.adapters.heuristic import HeuristicEngine

        return HeuristicEngine()
    raise NotImplementedError(f"prediction_engine={settings.prediction_engine} not wired")
