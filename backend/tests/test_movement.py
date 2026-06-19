from __future__ import annotations

from decimal import Decimal

from race_watcher.services.movement import evaluate_movement


def test_firmer_above_threshold_alerts() -> None:
    d = evaluate_movement(
        from_price=Decimal("3.40"), to_price=Decimal("3.00"), threshold_pct=Decimal("10")
    )
    assert d.alert is True
    assert d.direction == "firm"
    assert d.pct_change < 0


def test_drifter_above_threshold_alerts() -> None:
    d = evaluate_movement(
        from_price=Decimal("3.00"), to_price=Decimal("3.40"), threshold_pct=Decimal("10")
    )
    assert d.alert is True
    assert d.direction == "drift"
    assert d.pct_change > 0


def test_below_threshold_does_not_alert() -> None:
    d = evaluate_movement(
        from_price=Decimal("3.00"), to_price=Decimal("3.10"), threshold_pct=Decimal("10")
    )
    assert d.alert is False
    assert d.direction == "drift"


def test_flat_price_is_flat() -> None:
    d = evaluate_movement(
        from_price=Decimal("3.00"), to_price=Decimal("3.00"), threshold_pct=Decimal("10")
    )
    assert d.alert is False
    assert d.direction == "flat"


def test_zero_baseline_safe() -> None:
    d = evaluate_movement(
        from_price=Decimal("0"), to_price=Decimal("3.00"), threshold_pct=Decimal("10")
    )
    assert d.alert is False
    assert d.pct_change == Decimal("0")
