from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    confirm: bool


def parse_okx_candle_row(row: Sequence[str]) -> Candle:
    if len(row) < 9:
        raise ValueError(f"OKX candle row too short: expected >= 9 fields, got {len(row)}")
    return Candle(
        ts=int(row[0]),
        open=float(row[1]),
        high=float(row[2]),
        low=float(row[3]),
        close=float(row[4]),
        volume=float(row[5]),
        confirm=str(row[8]) == "1",
    )
