from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MovementDecision:
    """Outcome of evaluating a price against a prior reference."""

    alert: bool
    pct_change: Decimal
    direction: str  # "firm" | "drift" | "flat"


def _pct_change(from_price: Decimal, to_price: Decimal) -> Decimal:
    # firm = price falls = (to - from)/from is negative; we report the magnitude in pct_change
    # and capture direction separately.
    if from_price <= 0:
        return Decimal("0")
    return ((to_price - from_price) / from_price * Decimal("100")).quantize(Decimal("0.01"))


def evaluate_movement(
    *, from_price: Decimal, to_price: Decimal, threshold_pct: Decimal
) -> MovementDecision:
    pct = _pct_change(from_price, to_price)
    if pct < 0:
        direction = "firm"
    elif pct > 0:
        direction = "drift"
    else:
        direction = "flat"
    alert = abs(pct) >= threshold_pct
    return MovementDecision(alert=alert, pct_change=pct, direction=direction)
