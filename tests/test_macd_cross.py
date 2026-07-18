from __future__ import annotations

import pandas as pd

from helpers import make_candle
from traderhelper.config import WatchConfig
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.signals.dedup import DedupState
from traderhelper.signals.macd_cross import detect_macd_cross


def _snapshot(macd: list[float], signal: list[float]) -> IndicatorSnapshot:
    empty = pd.Series([0.0] * len(macd), dtype=float)
    return IndicatorSnapshot(
        closes=empty,
        highs=empty,
        lows=empty,
        macd=pd.Series(macd, dtype=float),
        macd_signal=pd.Series(signal, dtype=float),
        macd_hist=empty,
        rsi=empty,
        ema_fast=empty,
        ema_mid=empty,
        ema_slow=empty,
    )


def test_macd_bullish_cross(watch_macd: WatchConfig) -> None:
    state = DedupState()
    candles = [make_candle(1, 1.0), make_candle(2, 2.0)]
    signals = detect_macd_cross(
        watch_macd,
        candles,
        _snapshot(macd=[-1.0, 1.0], signal=[0.0, 0.0]),
        state,
    )
    assert len(signals) == 1
    assert signals[0].direction == "bullish"
    assert detect_macd_cross(
        watch_macd,
        candles,
        _snapshot(macd=[-1.0, 1.0], signal=[0.0, 0.0]),
        state,
    ) == []


def test_macd_bearish_cross(watch_macd: WatchConfig) -> None:
    state = DedupState()
    candles = [make_candle(1, 1.0), make_candle(2, 2.0)]
    signals = detect_macd_cross(
        watch_macd,
        candles,
        _snapshot(macd=[1.0, -1.0], signal=[0.0, 0.0]),
        state,
    )
    assert len(signals) == 1
    assert signals[0].direction == "bearish"
