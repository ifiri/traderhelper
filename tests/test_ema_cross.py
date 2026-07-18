from __future__ import annotations

import pandas as pd

from helpers import make_candle
from traderhelper.config import EmaConfig, WatchConfig
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.signals.dedup import DedupState
from traderhelper.signals.ema_cross import detect_ema_cross


def _snapshot(
    *,
    ema_fast: list[float],
    ema_mid: list[float],
    ema_slow: list[float],
    closes: list[float] | None = None,
) -> IndicatorSnapshot:
    size = len(ema_fast)
    close_values = closes if closes is not None else [0.0] * size
    empty = pd.Series([0.0] * size, dtype=float)
    return IndicatorSnapshot(
        closes=pd.Series(close_values, dtype=float),
        highs=empty,
        lows=empty,
        macd=empty,
        macd_signal=empty,
        macd_hist=empty,
        rsi=empty,
        ema_fast=pd.Series(ema_fast, dtype=float),
        ema_mid=pd.Series(ema_mid, dtype=float),
        ema_slow=pd.Series(ema_slow, dtype=float),
    )


def _watch() -> WatchConfig:
    return WatchConfig(
        inst_id="BTC-USDT",
        timeframe="1H",
        ema=EmaConfig(fast=20, mid=100, slow=200, cross=True),
    )


def test_ema_bullish_cross() -> None:
    state = DedupState()
    candles = [make_candle(1, 100.0), make_candle(2, 110.0)]
    signals = detect_ema_cross(
        _watch(),
        candles,
        _snapshot(
            ema_fast=[90.0, 105.0],
            ema_mid=[95.0, 100.0],
            ema_slow=[100.0, 100.0],
        ),
        state,
    )
    assert len(signals) == 1
    assert signals[0].direction == "bullish"
    assert signals[0].kind.value == "ema_cross"
    assert detect_ema_cross(
        _watch(),
        candles,
        _snapshot(
            ema_fast=[90.0, 105.0],
            ema_mid=[95.0, 100.0],
            ema_slow=[100.0, 100.0],
        ),
        state,
    ) == []


def test_ema_bearish_cross() -> None:
    state = DedupState()
    candles = [make_candle(1, 110.0), make_candle(2, 90.0)]
    signals = detect_ema_cross(
        _watch(),
        candles,
        _snapshot(
            ema_fast=[105.0, 95.0],
            ema_mid=[100.0, 100.0],
            ema_slow=[100.0, 100.0],
        ),
        state,
    )
    assert len(signals) == 1
    assert signals[0].direction == "bearish"


def test_ema_slow_break_bearish() -> None:
    state = DedupState()
    candles = [make_candle(1, 105.0), make_candle(2, 95.0)]
    signals = detect_ema_cross(
        _watch(),
        candles,
        _snapshot(
            ema_fast=[110.0, 108.0],
            ema_mid=[104.0, 103.0],
            ema_slow=[100.0, 100.0],
            closes=[105.0, 95.0],
        ),
        state,
    )
    assert len(signals) == 1
    assert signals[0].direction == "bearish"
    assert "broke below" in signals[0].body
