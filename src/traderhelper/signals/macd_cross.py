from __future__ import annotations

from traderhelper.config import WatchConfig, watch_key
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.market import Candle
from traderhelper.signals import Signal, SignalKind
from traderhelper.signals.crosses import macd_cross
from traderhelper.signals.dedup import DedupState


def detect_macd_cross(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    state: DedupState,
) -> list[Signal]:
    if not watch.macd_cross or len(candles) < 2:
        return []

    macd = snapshot.macd
    signal = snapshot.macd_signal
    if len(macd) < 2 or len(signal) < 2:
        return []

    direction = macd_cross(
        prev_macd=float(macd.iloc[-2]),
        prev_signal=float(signal.iloc[-2]),
        curr_macd=float(macd.iloc[-1]),
        curr_signal=float(signal.iloc[-1]),
    )
    if direction is None:
        return []

    candle = candles[-1]
    key = f"{watch_key(watch.inst_id, watch.timeframe)}:macd_cross"
    fingerprint = f"{direction.value}:{candle.ts}"
    if not state.should_emit(key, fingerprint):
        return []

    curr_macd = float(macd.iloc[-1])
    curr_signal = float(signal.iloc[-1])
    if direction.value == "bullish":
        title = "MACD bullish cross"
        body = f"MACD {curr_macd:.6g} crossed above signal {curr_signal:.6g}"
    else:
        title = "MACD bearish cross"
        body = f"MACD {curr_macd:.6g} crossed below signal {curr_signal:.6g}"

    return [
        Signal(
            kind=SignalKind.MACD_CROSS,
            inst_id=watch.inst_id,
            timeframe=watch.timeframe,
            direction=direction.value,
            title=title,
            body=body,
            candle_ts=candle.ts,
            price=candle.close,
        )
    ]
