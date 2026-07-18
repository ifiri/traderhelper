from __future__ import annotations

from dataclasses import dataclass

from traderhelper.config import ComboConditionKind, WatchConfig


@dataclass(slots=True, frozen=True)
class IndicatorNeeds:
    rsi: bool = False
    macd: bool = False
    ema: bool = False

    @property
    def any(self) -> bool:
        return self.rsi or self.macd or self.ema


def indicator_needs(watch: WatchConfig) -> IndicatorNeeds:
    divergence = watch.effective_divergence()
    need_rsi = (
        watch.rsi is not None
        or watch.combo_requires(ComboConditionKind.RSI)
        or (divergence is not None and divergence.rsi)
    )
    need_macd = (
        watch.macd_cross
        or watch.combo_requires(ComboConditionKind.MACD_CROSS)
        or (divergence is not None and divergence.macd)
    )
    need_ema = (watch.ema is not None and watch.ema.cross) or watch.combo_requires(
        ComboConditionKind.EMA_CROSS
    )
    return IndicatorNeeds(rsi=need_rsi, macd=need_macd, ema=need_ema)
