from __future__ import annotations

import pandas as pd

from helpers import make_candle
from traderhelper.config import WatchConfig
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.signals.dedup import DedupState
from traderhelper.signals.divergence import detect_divergences


def _snapshot(
    highs: list[float],
    lows: list[float],
    rsi: list[float],
) -> IndicatorSnapshot:
    size = len(highs)
    empty = pd.Series([0.0] * size, dtype=float)
    return IndicatorSnapshot(
        closes=empty,
        highs=pd.Series(highs, dtype=float),
        lows=pd.Series(lows, dtype=float),
        macd=empty,
        macd_signal=empty,
        macd_hist=empty,
        rsi=pd.Series(rsi, dtype=float),
        ema_fast=empty,
        ema_mid=empty,
        ema_slow=empty,
    )


def test_bearish_rsi_divergence(watch_divergence: WatchConfig) -> None:
    state = DedupState()
    candles = [make_candle(ts, close=10.0 + ts) for ts in range(7)]
    highs = [10.0, 12.0, 11.0, 14.0, 13.0, 12.5, 12.0]
    lows = [9.0] * 7
    rsi = [50.0, 70.0, 60.0, 65.0, 55.0, 54.0, 53.0]
    signals = detect_divergences(
        watch_divergence,
        candles,
        _snapshot(highs=highs, lows=lows, rsi=rsi),
        state,
    )
    bearish = [signal for signal in signals if signal.direction == "bearish"]
    assert len(bearish) == 1
    assert detect_divergences(
        watch_divergence,
        candles,
        _snapshot(highs=highs, lows=lows, rsi=rsi),
        state,
    ) == []


def test_bullish_rsi_divergence(watch_divergence: WatchConfig) -> None:
    state = DedupState()
    candles = [make_candle(ts, close=10.0) for ts in range(7)]
    highs = [15.0] * 7
    lows = [10.0, 8.0, 9.0, 6.0, 7.0, 7.5, 8.0]
    rsi = [50.0, 20.0, 30.0, 25.0, 35.0, 36.0, 37.0]
    signals = detect_divergences(
        watch_divergence,
        candles,
        _snapshot(highs=highs, lows=lows, rsi=rsi),
        state,
    )
    bullish = [signal for signal in signals if signal.direction == "bullish"]
    assert len(bullish) == 1
