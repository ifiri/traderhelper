from __future__ import annotations

import math
from dataclasses import dataclass

from traderhelper.config import (
    ComboConditionKind,
    ComboDirection,
    WatchConfig,
    watch_key,
)
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.market import Candle
from traderhelper.signals.divergence import find_active_divergences


@dataclass(slots=True)
class ActiveCondition:
    kind: ComboConditionKind
    direction: ComboDirection
    activated_ts: int
    activated_index: int
    valid: bool
    pivot_price: float | None = None
    fingerprint: str | None = None


class ConditionTracker:
    def __init__(self) -> None:
        self._conditions: dict[str, ActiveCondition] = {}

    def get(
        self,
        watch: WatchConfig,
        kind: ComboConditionKind,
        direction: ComboDirection,
    ) -> ActiveCondition | None:
        return self._conditions.get(_condition_key(watch, kind, direction))

    def set(self, watch: WatchConfig, condition: ActiveCondition) -> None:
        self._conditions[_condition_key(watch, condition.kind, condition.direction)] = (
            condition
        )

    def invalidate(
        self,
        watch: WatchConfig,
        kind: ComboConditionKind,
        direction: ComboDirection,
    ) -> None:
        key = _condition_key(watch, kind, direction)
        current = self._conditions.get(key)
        if current is not None:
            current.valid = False


def _condition_key(
    watch: WatchConfig,
    kind: ComboConditionKind,
    direction: ComboDirection,
) -> str:
    return f"{watch_key(watch.inst_id, watch.timeframe)}:cond:{kind.value}:{direction.value}"


def _activate(
    tracker: ConditionTracker,
    watch: WatchConfig,
    kind: ComboConditionKind,
    direction: ComboDirection,
    *,
    activated_ts: int,
    activated_index: int,
    pivot_price: float | None = None,
    fingerprint: str | None = None,
) -> None:
    existing = tracker.get(watch, kind, direction)
    if existing is not None and existing.valid:
        return
    tracker.set(
        watch,
        ActiveCondition(
            kind=kind,
            direction=direction,
            activated_ts=activated_ts,
            activated_index=activated_index,
            valid=True,
            pivot_price=pivot_price,
            fingerprint=fingerprint,
        ),
    )


def update_conditions(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    tracker: ConditionTracker,
) -> None:
    if not candles:
        return

    index = len(candles) - 1
    candle = candles[-1]
    ts = candle.ts
    close = candle.close

    _update_rsi(watch, snapshot, tracker, ts=ts, index=index)
    _update_ema(watch, candles, snapshot, tracker, ts=ts, index=index)
    _update_macd(watch, candles, snapshot, tracker, ts=ts, index=index)
    _update_divergence(watch, candles, snapshot, tracker, ts=ts, index=index, close=close)


def _update_rsi(
    watch: WatchConfig,
    snapshot: IndicatorSnapshot,
    tracker: ConditionTracker,
    *,
    ts: int,
    index: int,
) -> None:
    if watch.rsi is None and not watch.combo_requires(ComboConditionKind.RSI):
        return

    rsi_cfg = watch.effective_rsi()
    rsi_value = float(snapshot.rsi.iloc[-1])
    if math.isnan(rsi_value):
        return

    if rsi_value <= rsi_cfg.oversold:
        _activate(
            tracker,
            watch,
            ComboConditionKind.RSI,
            ComboDirection.BULLISH,
            activated_ts=ts,
            activated_index=index,
        )
    else:
        tracker.invalidate(watch, ComboConditionKind.RSI, ComboDirection.BULLISH)

    if rsi_value >= rsi_cfg.overbought:
        _activate(
            tracker,
            watch,
            ComboConditionKind.RSI,
            ComboDirection.BEARISH,
            activated_ts=ts,
            activated_index=index,
        )
    else:
        tracker.invalidate(watch, ComboConditionKind.RSI, ComboDirection.BEARISH)


def _update_ema(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    tracker: ConditionTracker,
    *,
    ts: int,
    index: int,
) -> None:
    ema_enabled = watch.ema is not None and watch.ema.cross
    if not ema_enabled and not watch.combo_requires(ComboConditionKind.EMA_CROSS):
        return
    if len(candles) < 2:
        return

    prev_fast = float(snapshot.ema_fast.iloc[-2])
    curr_fast = float(snapshot.ema_fast.iloc[-1])
    prev_slow = float(snapshot.ema_slow.iloc[-2])
    curr_slow = float(snapshot.ema_slow.iloc[-1])
    if any(math.isnan(value) for value in (prev_fast, curr_fast, prev_slow, curr_slow)):
        return

    if prev_fast <= prev_slow and curr_fast > curr_slow:
        _activate(
            tracker,
            watch,
            ComboConditionKind.EMA_CROSS,
            ComboDirection.BULLISH,
            activated_ts=ts,
            activated_index=index,
            fingerprint=f"cross:{ts}",
        )
        tracker.invalidate(watch, ComboConditionKind.EMA_CROSS, ComboDirection.BEARISH)
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        _activate(
            tracker,
            watch,
            ComboConditionKind.EMA_CROSS,
            ComboDirection.BEARISH,
            activated_ts=ts,
            activated_index=index,
            fingerprint=f"cross:{ts}",
        )
        tracker.invalidate(watch, ComboConditionKind.EMA_CROSS, ComboDirection.BULLISH)

    bullish = tracker.get(watch, ComboConditionKind.EMA_CROSS, ComboDirection.BULLISH)
    if bullish is not None and bullish.valid and curr_fast <= curr_slow:
        tracker.invalidate(watch, ComboConditionKind.EMA_CROSS, ComboDirection.BULLISH)

    bearish = tracker.get(watch, ComboConditionKind.EMA_CROSS, ComboDirection.BEARISH)
    if bearish is not None and bearish.valid and curr_fast >= curr_slow:
        tracker.invalidate(watch, ComboConditionKind.EMA_CROSS, ComboDirection.BEARISH)


def _update_macd(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    tracker: ConditionTracker,
    *,
    ts: int,
    index: int,
) -> None:
    if not watch.macd_cross and not watch.combo_requires(ComboConditionKind.MACD_CROSS):
        return
    if len(candles) < 2:
        return

    prev_macd = float(snapshot.macd.iloc[-2])
    prev_signal = float(snapshot.macd_signal.iloc[-2])
    curr_macd = float(snapshot.macd.iloc[-1])
    curr_signal = float(snapshot.macd_signal.iloc[-1])
    if any(math.isnan(value) for value in (prev_macd, prev_signal, curr_macd, curr_signal)):
        return

    prev_diff = prev_macd - prev_signal
    curr_diff = curr_macd - curr_signal

    if prev_diff <= 0 < curr_diff:
        _activate(
            tracker,
            watch,
            ComboConditionKind.MACD_CROSS,
            ComboDirection.BULLISH,
            activated_ts=ts,
            activated_index=index,
            fingerprint=f"cross:{ts}",
        )
        tracker.invalidate(watch, ComboConditionKind.MACD_CROSS, ComboDirection.BEARISH)
    elif prev_diff >= 0 > curr_diff:
        _activate(
            tracker,
            watch,
            ComboConditionKind.MACD_CROSS,
            ComboDirection.BEARISH,
            activated_ts=ts,
            activated_index=index,
            fingerprint=f"cross:{ts}",
        )
        tracker.invalidate(watch, ComboConditionKind.MACD_CROSS, ComboDirection.BULLISH)

    bullish = tracker.get(watch, ComboConditionKind.MACD_CROSS, ComboDirection.BULLISH)
    if bullish is not None and bullish.valid and curr_diff <= 0:
        tracker.invalidate(watch, ComboConditionKind.MACD_CROSS, ComboDirection.BULLISH)

    bearish = tracker.get(watch, ComboConditionKind.MACD_CROSS, ComboDirection.BEARISH)
    if bearish is not None and bearish.valid and curr_diff >= 0:
        tracker.invalidate(watch, ComboConditionKind.MACD_CROSS, ComboDirection.BEARISH)


def _update_divergence(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    tracker: ConditionTracker,
    *,
    ts: int,
    index: int,
    close: float,
) -> None:
    cfg = watch.effective_divergence()
    if cfg is None:
        return

    for found in find_active_divergences(cfg, candles, snapshot):
        direction = ComboDirection(found.direction)
        existing = tracker.get(watch, ComboConditionKind.DIVERGENCE, direction)
        if (
            existing is not None
            and not existing.valid
            and existing.fingerprint == found.fingerprint
        ):
            continue
        _activate(
            tracker,
            watch,
            ComboConditionKind.DIVERGENCE,
            direction,
            activated_ts=ts,
            activated_index=index,
            pivot_price=found.pivot_price,
            fingerprint=found.fingerprint,
        )

    for direction in (ComboDirection.BULLISH, ComboDirection.BEARISH):
        active = tracker.get(watch, ComboConditionKind.DIVERGENCE, direction)
        if active is None or not active.valid or active.pivot_price is None:
            continue
        if direction == ComboDirection.BULLISH and close < active.pivot_price:
            tracker.invalidate(watch, ComboConditionKind.DIVERGENCE, direction)
        elif direction == ComboDirection.BEARISH and close > active.pivot_price:
            tracker.invalidate(watch, ComboConditionKind.DIVERGENCE, direction)


def condition_in_window(
    active: ActiveCondition | None,
    *,
    window_start_index: int,
) -> bool:
    return (
        active is not None
        and active.valid
        and active.activated_index >= window_start_index
    )
