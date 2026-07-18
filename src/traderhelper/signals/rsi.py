from __future__ import annotations

import math

from traderhelper.config import WatchConfig, watch_key
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.market import Candle
from traderhelper.signals import Signal, SignalKind
from traderhelper.signals.dedup import DedupState


def arm_rsi_levels(
    watch: WatchConfig,
    snapshot: IndicatorSnapshot,
    state: DedupState,
) -> None:
    if watch.rsi is None:
        return
    rsi_value = float(snapshot.rsi.iloc[-1])
    if math.isnan(rsi_value):
        return
    base = watch_key(watch.inst_id, watch.timeframe)
    state.set_armed(f"{base}:rsi:overbought", rsi_value < watch.rsi.overbought)
    state.set_armed(f"{base}:rsi:oversold", rsi_value > watch.rsi.oversold)


def detect_rsi_levels(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    state: DedupState,
) -> list[Signal]:
    if watch.rsi is None or not candles:
        return []

    rsi_value = float(snapshot.rsi.iloc[-1])
    if math.isnan(rsi_value):
        return []

    candle = candles[-1]
    base = watch_key(watch.inst_id, watch.timeframe)
    signals: list[Signal] = []

    overbought_key = f"{base}:rsi:overbought"
    oversold_key = f"{base}:rsi:oversold"
    overbought_armed = state.is_armed(overbought_key)
    oversold_armed = state.is_armed(oversold_key)

    if rsi_value < watch.rsi.overbought:
        state.set_armed(overbought_key, True)
    if rsi_value > watch.rsi.oversold:
        state.set_armed(oversold_key, True)

    if rsi_value >= watch.rsi.overbought and overbought_armed:
        state.set_armed(overbought_key, False)
        signals.append(
            Signal(
                kind=SignalKind.RSI,
                inst_id=watch.inst_id,
                timeframe=watch.timeframe,
                direction="overbought",
                title="RSI overbought",
                body=f"RSI {rsi_value:.2f} >= {watch.rsi.overbought}",
                candle_ts=candle.ts,
                price=candle.close,
            )
        )
    elif rsi_value >= watch.rsi.overbought:
        state.set_armed(overbought_key, False)

    if rsi_value <= watch.rsi.oversold and oversold_armed:
        state.set_armed(oversold_key, False)
        signals.append(
            Signal(
                kind=SignalKind.RSI,
                inst_id=watch.inst_id,
                timeframe=watch.timeframe,
                direction="oversold",
                title="RSI oversold",
                body=f"RSI {rsi_value:.2f} <= {watch.rsi.oversold}",
                candle_ts=candle.ts,
                price=candle.close,
            )
        )
    elif rsi_value <= watch.rsi.oversold:
        state.set_armed(oversold_key, False)

    return signals
