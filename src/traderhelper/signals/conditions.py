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
from traderhelper.signals.crosses import CrossSide, line_cross, macd_cross, values_ready
from traderhelper.signals.divergence import find_active_divergences


@dataclass(slots=True)
class ActiveCondition:
    kind: ComboConditionKind
    direction: ComboDirection
    activated_ts: int
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

    candle = candles[-1]
    ts = candle.ts
    close = candle.close

    _update_rsi(watch, snapshot, tracker, ts=ts)
    _update_ema(watch, candles, snapshot, tracker, ts=ts)
    _update_macd(watch, candles, snapshot, tracker, ts=ts)
    _update_divergence(watch, candles, snapshot, tracker, ts=ts, close=close)


def _update_rsi(
    watch: WatchConfig,
    snapshot: IndicatorSnapshot,
    tracker: ConditionTracker,
    *,
    ts: int,
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

    cross = line_cross(prev_fast, prev_slow, curr_fast, curr_slow)
    if cross is CrossSide.BULLISH:
        _activate(
            tracker,
            watch,
            ComboConditionKind.EMA_CROSS,
            ComboDirection.BULLISH,
            activated_ts=ts,
            fingerprint=f"cross:{ts}",
        )
        tracker.invalidate(watch, ComboConditionKind.EMA_CROSS, ComboDirection.BEARISH)
    elif cross is CrossSide.BEARISH:
        _activate(
            tracker,
            watch,
            ComboConditionKind.EMA_CROSS,
            ComboDirection.BEARISH,
            activated_ts=ts,
            fingerprint=f"cross:{ts}",
        )
        tracker.invalidate(watch, ComboConditionKind.EMA_CROSS, ComboDirection.BULLISH)

    if values_ready(curr_fast, curr_slow):
        if curr_fast <= curr_slow:
            tracker.invalidate(
                watch, ComboConditionKind.EMA_CROSS, ComboDirection.BULLISH
            )
        if curr_fast >= curr_slow:
            tracker.invalidate(
                watch, ComboConditionKind.EMA_CROSS, ComboDirection.BEARISH
            )


def _update_macd(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    tracker: ConditionTracker,
    *,
    ts: int,
) -> None:
    if not watch.macd_cross and not watch.combo_requires(ComboConditionKind.MACD_CROSS):
        return
    if len(candles) < 2:
        return

    prev_macd = float(snapshot.macd.iloc[-2])
    prev_signal = float(snapshot.macd_signal.iloc[-2])
    curr_macd = float(snapshot.macd.iloc[-1])
    curr_signal = float(snapshot.macd_signal.iloc[-1])

    cross = macd_cross(
        prev_macd=prev_macd,
        prev_signal=prev_signal,
        curr_macd=curr_macd,
        curr_signal=curr_signal,
    )
    if cross is CrossSide.BULLISH:
        _activate(
            tracker,
            watch,
            ComboConditionKind.MACD_CROSS,
            ComboDirection.BULLISH,
            activated_ts=ts,
            fingerprint=f"cross:{ts}",
        )
        tracker.invalidate(watch, ComboConditionKind.MACD_CROSS, ComboDirection.BEARISH)
    elif cross is CrossSide.BEARISH:
        _activate(
            tracker,
            watch,
            ComboConditionKind.MACD_CROSS,
            ComboDirection.BEARISH,
            activated_ts=ts,
            fingerprint=f"cross:{ts}",
        )
        tracker.invalidate(watch, ComboConditionKind.MACD_CROSS, ComboDirection.BULLISH)

    if values_ready(curr_macd, curr_signal):
        curr_diff = curr_macd - curr_signal
        if curr_diff <= 0:
            tracker.invalidate(
                watch, ComboConditionKind.MACD_CROSS, ComboDirection.BULLISH
            )
        if curr_diff >= 0:
            tracker.invalidate(
                watch, ComboConditionKind.MACD_CROSS, ComboDirection.BEARISH
            )


def _update_divergence(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    tracker: ConditionTracker,
    *,
    ts: int,
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
    candles: list[Candle],
    *,
    window: int,
) -> bool:
    if active is None or not active.valid or not candles or window < 1:
        return False
    window_start_ts = candles[-window:][0].ts
    return active.activated_ts >= window_start_ts
