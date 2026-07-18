from __future__ import annotations

from traderhelper.config import WatchConfig, watch_key
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.market import Candle
from traderhelper.signals import Signal, SignalKind
from traderhelper.signals.crosses import ema_event
from traderhelper.signals.dedup import DedupState


def detect_ema_cross(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    state: DedupState,
) -> list[Signal]:
    if watch.ema is None or not watch.ema.cross or len(candles) < 2:
        return []

    event = ema_event(
        prev_fast=float(snapshot.ema_fast.iloc[-2]),
        curr_fast=float(snapshot.ema_fast.iloc[-1]),
        prev_slow=float(snapshot.ema_slow.iloc[-2]),
        curr_slow=float(snapshot.ema_slow.iloc[-1]),
        prev_close=float(candles[-2].close),
        curr_close=float(candles[-1].close),
    )
    if event is None:
        return []

    candle = candles[-1]
    key = f"{watch_key(watch.inst_id, watch.timeframe)}:ema_cross"
    fingerprint = f"{event.direction.value}:{event.kind}:{candle.ts}"
    if not state.should_emit(key, fingerprint):
        return []

    ema = watch.ema
    curr_fast = float(snapshot.ema_fast.iloc[-1])
    curr_mid = float(snapshot.ema_mid.iloc[-1])
    curr_slow = float(snapshot.ema_slow.iloc[-1])
    levels = (
        f"EMA{ema.fast}={curr_fast:.6g} EMA{ema.mid}={curr_mid:.6g} "
        f"EMA{ema.slow}={curr_slow:.6g}"
    )
    if event.kind == "cross":
        if event.direction.value == "bullish":
            title = "EMA bullish cross"
            body = f"EMA{ema.fast} crossed above EMA{ema.slow}. {levels}"
        else:
            title = "EMA bearish cross"
            body = f"EMA{ema.fast} crossed below EMA{ema.slow}. {levels}"
    elif event.direction.value == "bearish":
        title = "EMA slow break"
        body = f"Close broke below EMA{ema.slow}. {levels}"
    else:
        title = "EMA slow break"
        body = f"Close broke above EMA{ema.slow}. {levels}"

    return [
        Signal(
            kind=SignalKind.EMA_CROSS,
            inst_id=watch.inst_id,
            timeframe=watch.timeframe,
            direction=event.direction.value,
            title=title,
            body=body,
            candle_ts=candle.ts,
            price=candle.close,
        )
    ]
