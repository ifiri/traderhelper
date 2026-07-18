from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class CrossSide(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass(slots=True, frozen=True)
class EmaEvent:
    direction: CrossSide
    kind: str


def values_ready(*values: float) -> bool:
    return not any(math.isnan(value) for value in values)


def line_cross(
    prev_fast: float,
    prev_slow: float,
    curr_fast: float,
    curr_slow: float,
) -> CrossSide | None:
    if not values_ready(prev_fast, prev_slow, curr_fast, curr_slow):
        return None
    prev_diff = prev_fast - prev_slow
    curr_diff = curr_fast - curr_slow
    if prev_diff <= 0 < curr_diff:
        return CrossSide.BULLISH
    if prev_diff >= 0 > curr_diff:
        return CrossSide.BEARISH
    return None


def ema_event(
    *,
    prev_fast: float,
    curr_fast: float,
    prev_slow: float,
    curr_slow: float,
    prev_close: float,
    curr_close: float,
) -> EmaEvent | None:
    cross = line_cross(prev_fast, prev_slow, curr_fast, curr_slow)
    if cross is not None:
        return EmaEvent(direction=cross, kind="cross")

    if not values_ready(prev_fast, curr_fast, prev_slow, curr_slow, prev_close, curr_close):
        return None

    if prev_fast > prev_slow and prev_close >= prev_slow and curr_close < curr_slow:
        return EmaEvent(direction=CrossSide.BEARISH, kind="break")
    if prev_fast < prev_slow and prev_close <= prev_slow and curr_close > curr_slow:
        return EmaEvent(direction=CrossSide.BULLISH, kind="break")
    return None


def macd_cross(
    *,
    prev_macd: float,
    prev_signal: float,
    curr_macd: float,
    curr_signal: float,
) -> CrossSide | None:
    return line_cross(prev_macd, prev_signal, curr_macd, curr_signal)

