from __future__ import annotations

from traderhelper.config import WatchConfig
from traderhelper.signals.dedup import DedupState
from traderhelper.signals.price import arm_price_alerts, detect_price_alerts


def test_price_above_fires_once_until_reset(watch_price: WatchConfig) -> None:
    state = DedupState()
    arm_price_alerts(watch_price, price=95.0, state=state)

    first = detect_price_alerts(watch_price, price=100.0, state=state)
    assert len(first) == 1
    assert first[0].direction == "above"

    second = detect_price_alerts(watch_price, price=101.0, state=state)
    assert second == []

    detect_price_alerts(watch_price, price=99.0, state=state)
    third = detect_price_alerts(watch_price, price=100.0, state=state)
    assert len(third) == 1


def test_price_below_requires_arm(watch_price: WatchConfig) -> None:
    state = DedupState()
    arm_price_alerts(watch_price, price=85.0, state=state)
    assert detect_price_alerts(watch_price, price=80.0, state=state) == []

    detect_price_alerts(watch_price, price=91.0, state=state)
    fired = detect_price_alerts(watch_price, price=90.0, state=state)
    assert len(fired) == 1
    assert fired[0].direction == "below"
