from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pandas_ta as ta

from traderhelper.indicators.needs import IndicatorNeeds
from traderhelper.market import Candle


@dataclass(slots=True, frozen=True)
class IndicatorSnapshot:
    closes: pd.Series
    highs: pd.Series
    lows: pd.Series
    macd: pd.Series
    macd_signal: pd.Series
    macd_hist: pd.Series
    rsi: pd.Series
    ema_fast: pd.Series
    ema_mid: pd.Series
    ema_slow: pd.Series


def _pick_macd_columns(
    macd_df: pd.DataFrame,
    macd_fast: int,
    macd_slow: int,
    macd_signal: int,
) -> tuple[str, str, str]:
    macd_col = f"MACD_{macd_fast}_{macd_slow}_{macd_signal}"
    signal_col = f"MACDs_{macd_fast}_{macd_slow}_{macd_signal}"
    hist_col = f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"
    if macd_col in macd_df.columns and signal_col in macd_df.columns and hist_col in macd_df.columns:
        return macd_col, signal_col, hist_col

    columns = list(macd_df.columns)
    resolved_macd = next(
        (
            col
            for col in columns
            if col.startswith("MACD_")
            and not col.startswith("MACDh_")
            and not col.startswith("MACDs_")
        ),
        None,
    )
    resolved_signal = next((col for col in columns if col.startswith("MACDs_")), None)
    resolved_hist = next((col for col in columns if col.startswith("MACDh_")), None)
    if resolved_macd is None or resolved_signal is None or resolved_hist is None:
        raise ValueError(f"unexpected MACD columns: {columns}")
    return resolved_macd, resolved_signal, resolved_hist


def _empty_series(size: int) -> pd.Series:
    return pd.Series([float("nan")] * size, dtype=float)


def compute_indicators(
    candles: list[Candle],
    *,
    needs: IndicatorNeeds | None = None,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    ema_fast: int = 20,
    ema_mid: int = 100,
    ema_slow: int = 200,
) -> IndicatorSnapshot | None:
    required = needs if needs is not None else IndicatorNeeds(rsi=True, macd=True, ema=True)
    if not required.any:
        return None

    lengths: list[int] = []
    if required.macd:
        lengths.append(macd_slow + macd_signal)
    if required.rsi:
        lengths.append(rsi_period)
    if required.ema:
        lengths.append(ema_slow)
    min_candles = max(lengths) + 5
    if len(candles) < min_candles:
        return None

    frame = pd.DataFrame(
        {
            "close": [candle.close for candle in candles],
            "high": [candle.high for candle in candles],
            "low": [candle.low for candle in candles],
        }
    )
    closes = frame["close"]
    size = len(closes)

    macd_series = _empty_series(size)
    macd_signal_series = _empty_series(size)
    macd_hist_series = _empty_series(size)
    if required.macd:
        macd_df = ta.macd(
            closes,
            fast=macd_fast,
            slow=macd_slow,
            signal=macd_signal,
        )
        if macd_df is None or macd_df.empty:
            return None
        try:
            macd_col, signal_col, hist_col = _pick_macd_columns(
                macd_df, macd_fast, macd_slow, macd_signal
            )
        except ValueError:
            return None
        macd_series = macd_df[macd_col]
        macd_signal_series = macd_df[signal_col]
        macd_hist_series = macd_df[hist_col]

    rsi_series = _empty_series(size)
    if required.rsi:
        computed_rsi = ta.rsi(closes, length=rsi_period)
        if computed_rsi is None:
            return None
        rsi_series = computed_rsi

    ema_fast_series = _empty_series(size)
    ema_mid_series = _empty_series(size)
    ema_slow_series = _empty_series(size)
    if required.ema:
        computed_fast = ta.ema(closes, length=ema_fast)
        computed_mid = ta.ema(closes, length=ema_mid)
        computed_slow = ta.ema(closes, length=ema_slow)
        if computed_fast is None or computed_mid is None or computed_slow is None:
            return None
        ema_fast_series = computed_fast
        ema_mid_series = computed_mid
        ema_slow_series = computed_slow

    return IndicatorSnapshot(
        closes=closes,
        highs=frame["high"],
        lows=frame["low"],
        macd=macd_series,
        macd_signal=macd_signal_series,
        macd_hist=macd_hist_series,
        rsi=rsi_series,
        ema_fast=ema_fast_series,
        ema_mid=ema_mid_series,
        ema_slow=ema_slow_series,
    )
