from __future__ import annotations

import pandas as pd

from helpers import make_candle
from traderhelper.config import WatchConfig
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.signals.dedup import DedupState
from traderhelper.signals.rsi import arm_rsi_levels, detect_rsi_levels


def _snapshot(rsi_values: list[float]) -> IndicatorSnapshot:
    series = pd.Series(rsi_values, dtype=float)
    empty = pd.Series([0.0] * len(rsi_values), dtype=float)
    return IndicatorSnapshot(
        closes=empty,
        highs=empty,
        lows=empty,
        macd=empty,
        macd_signal=empty,
        macd_hist=empty,
        rsi=series,
        ema_fast=empty,
        ema_mid=empty,
        ema_slow=empty,
    )


def test_rsi_overbought_fires_once_until_reset(watch_rsi: WatchConfig) -> None:
    state = DedupState()
    candles = [make_candle(1, 100.0)]
    arm_rsi_levels(watch_rsi, _snapshot([50.0]), state)

    first = detect_rsi_levels(watch_rsi, candles, _snapshot([75.0]), state)
    assert len(first) == 1
    assert first[0].direction == "overbought"

    second = detect_rsi_levels(watch_rsi, candles, _snapshot([80.0]), state)
    assert second == []

    detect_rsi_levels(watch_rsi, candles, _snapshot([60.0]), state)
    third = detect_rsi_levels(watch_rsi, candles, _snapshot([71.0]), state)
    assert len(third) == 1
