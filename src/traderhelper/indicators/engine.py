from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pandas_ta as ta

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


def compute_indicators(
    candles: list[Candle],
    *,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    ema_fast: int = 20,
    ema_mid: int = 100,
    ema_slow: int = 200,
) -> IndicatorSnapshot | None:
    min_candles = max(macd_slow + macd_signal, rsi_period, ema_slow) + 5
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

    rsi_series = ta.rsi(closes, length=rsi_period)
    if rsi_series is None:
        return None

    ema_fast_series = ta.ema(closes, length=ema_fast)
    ema_mid_series = ta.ema(closes, length=ema_mid)
    ema_slow_series = ta.ema(closes, length=ema_slow)
    if ema_fast_series is None or ema_mid_series is None or ema_slow_series is None:
        return None

    return IndicatorSnapshot(
        closes=closes,
        highs=frame["high"],
        lows=frame["low"],
        macd=macd_df[macd_col],
        macd_signal=macd_df[signal_col],
        macd_hist=macd_df[hist_col],
        rsi=rsi_series,
        ema_fast=ema_fast_series,
        ema_mid=ema_mid_series,
        ema_slow=ema_slow_series,
    )
