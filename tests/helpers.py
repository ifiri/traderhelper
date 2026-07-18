from __future__ import annotations

from traderhelper.market import Candle


def make_candle(
    ts: int,
    close: float,
    *,
    high: float | None = None,
    low: float | None = None,
    confirm: bool = True,
) -> Candle:
    return Candle(
        ts=ts,
        open=close,
        high=close if high is None else high,
        low=close if low is None else low,
        close=close,
        volume=1.0,
        confirm=confirm,
    )
