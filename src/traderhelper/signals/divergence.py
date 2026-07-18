from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from traderhelper.config import DivergenceConfig, WatchConfig, watch_key
from traderhelper.indicators import IndicatorSnapshot
from traderhelper.market import Candle
from traderhelper.signals import Signal, SignalKind
from traderhelper.signals.dedup import DedupState


@dataclass(slots=True, frozen=True)
class Pivot:
    index: int
    ts: int
    price: float
    indicator: float


@dataclass(slots=True, frozen=True)
class FoundDivergence:
    source_name: str
    direction: str
    older: Pivot
    newer: Pivot
    fingerprint: str
    pivot_price: float
    title: str
    body: str


def _is_pivot_high(series: pd.Series, index: int, left: int, right: int) -> bool:
    value = float(series.iloc[index])
    if math.isnan(value):
        return False
    for offset in range(1, left + 1):
        neighbor = float(series.iloc[index - offset])
        if math.isnan(neighbor) or neighbor >= value:
            return False
    for offset in range(1, right + 1):
        neighbor = float(series.iloc[index + offset])
        if math.isnan(neighbor) or neighbor > value:
            return False
    return True


def _is_pivot_low(series: pd.Series, index: int, left: int, right: int) -> bool:
    value = float(series.iloc[index])
    if math.isnan(value):
        return False
    for offset in range(1, left + 1):
        neighbor = float(series.iloc[index - offset])
        if math.isnan(neighbor) or neighbor <= value:
            return False
    for offset in range(1, right + 1):
        neighbor = float(series.iloc[index + offset])
        if math.isnan(neighbor) or neighbor < value:
            return False
    return True


def _collect_pivots(
    candles: list[Candle],
    price_series: pd.Series,
    indicator_series: pd.Series,
    *,
    lookback: int,
    left: int,
    right: int,
    find_highs: bool,
) -> list[Pivot]:
    end = len(price_series) - right - 1
    start = max(left, end - lookback + 1)
    pivots: list[Pivot] = []
    for index in range(start, end + 1):
        price = float(price_series.iloc[index])
        indicator = float(indicator_series.iloc[index])
        if math.isnan(price) or math.isnan(indicator):
            continue
        is_pivot = (
            _is_pivot_high(price_series, index, left, right)
            if find_highs
            else _is_pivot_low(price_series, index, left, right)
        )
        if is_pivot:
            pivots.append(
                Pivot(
                    index=index,
                    ts=candles[index].ts,
                    price=price,
                    indicator=indicator,
                )
            )
    return pivots


def _last_confirmed_pivot_pair(pivots: list[Pivot]) -> tuple[Pivot, Pivot] | None:
    if len(pivots) < 2:
        return None
    return pivots[-2], pivots[-1]


def find_active_divergences(
    cfg: DivergenceConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
) -> list[FoundDivergence]:
    if not candles:
        return []

    found: list[FoundDivergence] = []
    sources: list[tuple[str, pd.Series]] = []
    if cfg.rsi:
        sources.append(("rsi", snapshot.rsi))
    if cfg.macd:
        sources.append(("macd", snapshot.macd))

    for source_name, indicator in sources:
        bearish = _collect_pivots(
            candles,
            snapshot.highs,
            indicator,
            lookback=cfg.lookback,
            left=cfg.pivot_left,
            right=cfg.pivot_right,
            find_highs=True,
        )
        pair = _last_confirmed_pivot_pair(bearish)
        if pair is not None:
            older, newer = pair
            if newer.price > older.price and newer.indicator < older.indicator:
                found.append(
                    FoundDivergence(
                        source_name=source_name,
                        direction="bearish",
                        older=older,
                        newer=newer,
                        fingerprint=f"{source_name}:{older.ts}:{newer.ts}:bearish",
                        pivot_price=newer.price,
                        title=f"Bearish {source_name.upper()} divergence",
                        body=(
                            f"Price HH {older.price:.6g} -> {newer.price:.6g}, "
                            f"{source_name.upper()} LH {older.indicator:.6g} -> {newer.indicator:.6g}"
                        ),
                    )
                )

        bullish = _collect_pivots(
            candles,
            snapshot.lows,
            indicator,
            lookback=cfg.lookback,
            left=cfg.pivot_left,
            right=cfg.pivot_right,
            find_highs=False,
        )
        pair = _last_confirmed_pivot_pair(bullish)
        if pair is not None:
            older, newer = pair
            if newer.price < older.price and newer.indicator > older.indicator:
                found.append(
                    FoundDivergence(
                        source_name=source_name,
                        direction="bullish",
                        older=older,
                        newer=newer,
                        fingerprint=f"{source_name}:{older.ts}:{newer.ts}:bullish",
                        pivot_price=newer.price,
                        title=f"Bullish {source_name.upper()} divergence",
                        body=(
                            f"Price LL {older.price:.6g} -> {newer.price:.6g}, "
                            f"{source_name.upper()} HL {older.indicator:.6g} -> {newer.indicator:.6g}"
                        ),
                    )
                )

    return found


def detect_divergences(
    watch: WatchConfig,
    candles: list[Candle],
    snapshot: IndicatorSnapshot,
    state: DedupState,
) -> list[Signal]:
    if watch.divergence is None or not candles:
        return []

    signals: list[Signal] = []
    candle = candles[-1]
    base = watch_key(watch.inst_id, watch.timeframe)

    for item in find_active_divergences(watch.divergence, candles, snapshot):
        key = f"{base}:div:{item.source_name}:{item.direction}"
        fingerprint = f"{item.older.ts}:{item.newer.ts}"
        if state.should_emit(key, fingerprint):
            signals.append(
                Signal(
                    kind=SignalKind.DIVERGENCE,
                    inst_id=watch.inst_id,
                    timeframe=watch.timeframe,
                    direction=item.direction,
                    title=item.title,
                    body=item.body,
                    candle_ts=candle.ts,
                    price=candle.close,
                )
            )

    return signals
