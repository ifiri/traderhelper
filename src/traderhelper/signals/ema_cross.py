from __future__ import annotations

import math

from traderhelper.config import WatchConfig, watch_key
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.market import Candle
from traderhelper.signals import Signal, SignalKind
from traderhelper.signals.dedup import DedupState


def detect_ema_cross(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    state: DedupState,
) -> list[Signal]:
    if watch.ema is None or not watch.ema.cross or len(candles) < 2:
        return []

    prev_fast = float(snapshot.ema_fast.iloc[-2])
    curr_fast = float(snapshot.ema_fast.iloc[-1])
    prev_slow = float(snapshot.ema_slow.iloc[-2])
    curr_slow = float(snapshot.ema_slow.iloc[-1])
    curr_mid = float(snapshot.ema_mid.iloc[-1])
    prev_close = float(candles[-2].close)
    curr_close = float(candles[-1].close)
    values = (
        prev_fast,
        curr_fast,
        prev_slow,
        curr_slow,
        curr_mid,
        prev_close,
        curr_close,
    )
    if any(math.isnan(value) for value in values):
        return []

    candle = candles[-1]
    key = f"{watch_key(watch.inst_id, watch.timeframe)}:ema_cross"
    fingerprint = str(candle.ts)
    ema = watch.ema
    levels = (
        f"EMA{ema.fast}={curr_fast:.6g} EMA{ema.mid}={curr_mid:.6g} "
        f"EMA{ema.slow}={curr_slow:.6g}"
    )

    if prev_fast <= prev_slow and curr_fast > curr_slow:
        return _emit(
            watch,
            state,
            key=key,
            fingerprint=f"bullish:cross:{fingerprint}",
            direction="bullish",
            title="EMA bullish cross",
            body=f"EMA{ema.fast} crossed above EMA{ema.slow}. {levels}",
            candle=candle,
        )

    if prev_fast >= prev_slow and curr_fast < curr_slow:
        return _emit(
            watch,
            state,
            key=key,
            fingerprint=f"bearish:cross:{fingerprint}",
            direction="bearish",
            title="EMA bearish cross",
            body=f"EMA{ema.fast} crossed below EMA{ema.slow}. {levels}",
            candle=candle,
        )

    if prev_fast > prev_slow and prev_close >= prev_slow and curr_close < curr_slow:
        return _emit(
            watch,
            state,
            key=key,
            fingerprint=f"bearish:break:{fingerprint}",
            direction="bearish",
            title="EMA slow break",
            body=f"Close broke below EMA{ema.slow}. {levels}",
            candle=candle,
        )

    if prev_fast < prev_slow and prev_close <= prev_slow and curr_close > curr_slow:
        return _emit(
            watch,
            state,
            key=key,
            fingerprint=f"bullish:break:{fingerprint}",
            direction="bullish",
            title="EMA slow break",
            body=f"Close broke above EMA{ema.slow}. {levels}",
            candle=candle,
        )

    return []


def _emit(
    watch: WatchConfig,
    state: DedupState,
    *,
    key: str,
    fingerprint: str,
    direction: str,
    title: str,
    body: str,
    candle: Candle,
) -> list[Signal]:
    if not state.should_emit(key, fingerprint):
        return []
    return [
        Signal(
            kind=SignalKind.EMA_CROSS,
            inst_id=watch.inst_id,
            timeframe=watch.timeframe,
            direction=direction,
            title=title,
            body=body,
            candle_ts=candle.ts,
            price=candle.close,
        )
    ]
