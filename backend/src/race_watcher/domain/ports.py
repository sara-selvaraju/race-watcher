from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from race_watcher.domain.models import (
    DomainMeeting,
    DomainPrediction,
    DomainPrice,
    DomainRunner,
)


@runtime_checkable
class RaceCardSource(Protocol):
    """Loads meetings/races/runners/form. Source of truth for the field."""

    name: str

    def load_meeting(self) -> DomainMeeting: ...


@runtime_checkable
class OddsSource(Protocol):
    """Returns current prices keyed by (race_number, runner_number)."""

    name: str

    def fetch_prices(self, meeting: DomainMeeting) -> list[DomainPrice]: ...


@runtime_checkable
class PredictionEngine(Protocol):
    """Computes a rating/win_prob per runner."""

    name: str

    def predict(self, race_runners: Iterable[DomainRunner]) -> list[DomainPrediction]: ...
