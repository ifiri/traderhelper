from __future__ import annotations

from traderhelper.config import WatchConfig, watch_key
from traderhelper.market import Candle
from traderhelper.signals import Signal, SignalKind
from traderhelper.signals.conditions import ConditionTracker, condition_in_window
from traderhelper.signals.dedup import DedupState


def detect_combo(
    watch: WatchConfig,
    candles: list[Candle],
    tracker: ConditionTracker,
    state: DedupState,
) -> list[Signal]:
    if not watch.combo or not candles:
        return []

    candle = candles[-1]
    current_index = len(candles) - 1
    signals: list[Signal] = []
    base = watch_key(watch.inst_id, watch.timeframe)

    for rule in watch.combo:
        window_start_index = max(0, current_index - rule.window + 1)
        matched: list[str] = []
        activation_ts: list[int] = []
        all_matched = True

        for condition in rule.require:
            active = tracker.get(watch, condition.kind, condition.direction)
            if not condition_in_window(active, window_start_index=window_start_index):
                all_matched = False
                break
            assert active is not None
            matched.append(f"{condition.kind.value}:{condition.direction.value}")
            activation_ts.append(active.activated_ts)

        if not all_matched:
            continue

        fingerprint = f"{rule.name}:{':'.join(str(ts) for ts in sorted(activation_ts))}"
        dedup_key = f"{base}:combo:{rule.name}"
        if not state.should_emit(dedup_key, fingerprint):
            continue

        body_lines = [
            f"Window={rule.window} candles",
            "Matched: " + ", ".join(matched),
        ]
        direction = _combo_direction(matched)
        signals.append(
            Signal(
                kind=SignalKind.COMBO,
                inst_id=watch.inst_id,
                timeframe=watch.timeframe,
                direction=direction,
                title=f"Combo: {rule.name}",
                body="\n".join(body_lines),
                candle_ts=candle.ts,
                price=candle.close,
            )
        )

    return signals


def _combo_direction(matched: list[str]) -> str:
    bullish = sum(1 for item in matched if item.endswith(":bullish"))
    bearish = sum(1 for item in matched if item.endswith(":bearish"))
    if bullish and not bearish:
        return "bullish"
    if bearish and not bullish:
        return "bearish"
    return "mixed"
