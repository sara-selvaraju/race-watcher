from __future__ import annotations

import random
from datetime import UTC, datetime
from decimal import Decimal

from race_watcher.domain.models import DomainMeeting, DomainPrice


class MockOddsAdapter:
    """Local-dev odds source: jitters seed prices each call so the worker has something to write."""

    name = "mock"

    def __init__(self, jitter_pct: float = 5.0, seed: int | None = None):
        self.jitter_pct = jitter_pct
        self._rng = random.Random(seed)

    def fetch_prices(self, meeting: DomainMeeting) -> list[DomainPrice]:
        now = datetime.now(UTC)
        out: list[DomainPrice] = []
        for race in meeting.races:
            for runner in race.runners:
                base = runner.seed_price
                if base is None:
                    continue
                jitter = Decimal(str(1 + self._rng.uniform(-self.jitter_pct, self.jitter_pct) / 100))
                price = (base * jitter).quantize(Decimal("0.01"))
                out.append(
                    DomainPrice(
                        race_number=race.number,
                        runner_number=runner.number,
                        price=price,
                        source="mock",
                        taken_at=now,
                    )
                )
        return out
