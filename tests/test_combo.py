from __future__ import annotations

import pandas as pd

from helpers import make_candle
from traderhelper.config import (
    ComboCondition,
    ComboConditionKind,
    ComboDirection,
    ComboRuleConfig,
    EmaConfig,
    RsiConfig,
    WatchConfig,
)
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.signals.combo import detect_combo
from traderhelper.signals.conditions import ConditionTracker, update_conditions
from traderhelper.signals.dedup import DedupState
from traderhelper.signals.rsi import detect_rsi_levels


def _snapshot(
    *,
    rsi: list[float],
    ema_fast: list[float],
    ema_slow: list[float],
    macd: list[float] | None = None,
    macd_signal: list[float] | None = None,
) -> IndicatorSnapshot:
    size = len(rsi)
    empty = pd.Series([0.0] * size, dtype=float)
    mid = [(fast + slow) / 2 for fast, slow in zip(ema_fast, ema_slow)]
    return IndicatorSnapshot(
        closes=empty,
        highs=empty,
        lows=empty,
        macd=pd.Series(macd if macd is not None else [0.0] * size, dtype=float),
        macd_signal=pd.Series(
            macd_signal if macd_signal is not None else [0.0] * size, dtype=float
        ),
        macd_hist=empty,
        rsi=pd.Series(rsi, dtype=float),
        ema_fast=pd.Series(ema_fast, dtype=float),
        ema_mid=pd.Series(mid, dtype=float),
        ema_slow=pd.Series(ema_slow, dtype=float),
    )


def _watch_combo() -> WatchConfig:
    return WatchConfig(
        inst_id="BTC-USDT",
        timeframe="1H",
        rsi=RsiConfig(period=14, overbought=70, oversold=30),
        ema=EmaConfig(cross=True),
        combo=[
            ComboRuleConfig(
                name="bull confluence",
                window=5,
                require=[
                    ComboCondition(
                        kind=ComboConditionKind.RSI,
                        direction=ComboDirection.BULLISH,
                    ),
                    ComboCondition(
                        kind=ComboConditionKind.EMA_CROSS,
                        direction=ComboDirection.BULLISH,
                    ),
                ],
            )
        ],
    )


def test_combo_fires_when_conditions_active_in_window() -> None:
    watch = _watch_combo()
    tracker = ConditionTracker()
    state = DedupState()
    candles = [make_candle(ts, 100.0) for ts in range(1, 6)]

    update_conditions(
        watch,
        candles[:2],
        _snapshot(
            rsi=[50.0, 25.0],
            ema_fast=[90.0, 90.0],
            ema_slow=[100.0, 100.0],
        ),
        tracker,
    )
    update_conditions(
        watch,
        candles[:4],
        _snapshot(
            rsi=[50.0, 25.0, 24.0, 23.0],
            ema_fast=[90.0, 90.0, 95.0, 105.0],
            ema_slow=[100.0, 100.0, 100.0, 100.0],
        ),
        tracker,
    )

    signals = detect_combo(watch, candles[:4], tracker, state)
    assert len(signals) == 1
    assert signals[0].kind.value == "combo"
    assert signals[0].direction == "bullish"
    assert detect_combo(watch, candles[:4], tracker, state) == []


def test_combo_blocked_when_rsi_leaves_oversold() -> None:
    watch = _watch_combo()
    tracker = ConditionTracker()
    state = DedupState()
    candles = [make_candle(ts, 100.0) for ts in range(1, 6)]

    update_conditions(
        watch,
        candles[:2],
        _snapshot(
            rsi=[50.0, 25.0],
            ema_fast=[90.0, 105.0],
            ema_slow=[100.0, 100.0],
        ),
        tracker,
    )
    update_conditions(
        watch,
        candles[:3],
        _snapshot(
            rsi=[50.0, 25.0, 40.0],
            ema_fast=[90.0, 105.0, 106.0],
            ema_slow=[100.0, 100.0, 100.0],
        ),
        tracker,
    )

    assert detect_combo(watch, candles[:3], tracker, state) == []


def test_combo_blocked_when_divergence_closes() -> None:
    from traderhelper.config import DivergenceConfig
    from traderhelper.signals.conditions import ActiveCondition

    watch = WatchConfig(
        inst_id="BTC-USDT",
        timeframe="1H",
        ema=EmaConfig(cross=True),
        divergence=DivergenceConfig(rsi=True, macd=False, pivot_left=1, pivot_right=1),
        combo=[
            ComboRuleConfig(
                name="div ema",
                window=5,
                require=[
                    ComboCondition(
                        kind=ComboConditionKind.DIVERGENCE,
                        direction=ComboDirection.BULLISH,
                    ),
                    ComboCondition(
                        kind=ComboConditionKind.EMA_CROSS,
                        direction=ComboDirection.BULLISH,
                    ),
                ],
            )
        ],
    )
    tracker = ConditionTracker()
    state = DedupState()
    candles = [make_candle(ts, close=10.0) for ts in range(1, 5)]

    tracker.set(
        watch,
        ActiveCondition(
            kind=ComboConditionKind.DIVERGENCE,
            direction=ComboDirection.BULLISH,
            activated_ts=1,
            valid=True,
            pivot_price=8.0,
            fingerprint="rsi:1:2:bullish",
        ),
    )
    update_conditions(
        watch,
        candles[:2],
        _snapshot(
            rsi=[50.0, 50.0],
            ema_fast=[90.0, 105.0],
            ema_slow=[100.0, 100.0],
        ),
        tracker,
    )
    broken = [make_candle(1, 10.0), make_candle(2, 7.0)]
    update_conditions(
        watch,
        broken,
        _snapshot(
            rsi=[50.0, 50.0],
            ema_fast=[105.0, 106.0],
            ema_slow=[100.0, 100.0],
        ),
        tracker,
    )
    assert detect_combo(watch, broken, tracker, state) == []


def test_combo_window_uses_activation_timestamp() -> None:
    watch = _watch_combo()
    tracker = ConditionTracker()
    state = DedupState()
    candles = [make_candle(ts, 100.0) for ts in range(1, 12)]

    update_conditions(
        watch,
        candles[:2],
        _snapshot(
            rsi=[50.0, 25.0],
            ema_fast=[90.0, 105.0],
            ema_slow=[100.0, 100.0],
        ),
        tracker,
    )
    for end in range(3, 11):
        update_conditions(
            watch,
            candles[:end],
            _snapshot(
                rsi=[50.0] + [25.0] * (end - 1),
                ema_fast=[90.0, 105.0] + [106.0] * (end - 2),
                ema_slow=[100.0] * end,
            ),
            tracker,
        )

    assert detect_combo(watch, candles[:10], tracker, state) == []

    update_conditions(
        watch,
        candles[:11],
        _snapshot(
            rsi=[50.0] + [25.0] * 10,
            ema_fast=[90.0, 105.0] + [106.0] * 9,
            ema_slow=[100.0] * 11,
        ),
        tracker,
    )
    assert detect_combo(watch, candles[:11], tracker, state) == []


def test_standalone_rsi_still_emits_with_combo() -> None:
    watch = _watch_combo()
    state = DedupState()
    candles = [make_candle(1, 100.0)]
    from traderhelper.signals.rsi import arm_rsi_levels

    arm_rsi_levels(
        watch,
        _snapshot(rsi=[50.0], ema_fast=[100.0], ema_slow=[100.0]),
        state,
    )
    signals = detect_rsi_levels(
        watch,
        candles,
        _snapshot(rsi=[25.0], ema_fast=[100.0], ema_slow=[100.0]),
        state,
    )
    assert len(signals) == 1
    assert signals[0].kind.value == "rsi"
