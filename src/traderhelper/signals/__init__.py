from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class SignalKind(str, Enum):
    PRICE = "price"
    MACD_CROSS = "macd_cross"
    RSI = "rsi"
    DIVERGENCE = "divergence"
    EMA_CROSS = "ema_cross"
    COMBO = "combo"


@dataclass(slots=True, frozen=True)
class Signal:
    kind: SignalKind
    inst_id: str
    timeframe: str
    direction: str
    title: str
    body: str
    candle_ts: int | None = None
    price: float | None = None

    def format_message(self) -> str:
        lines = [
            f"<b>{self.title}</b>",
            f"{self.inst_id} · {self.timeframe}",
            self.body,
        ]
        if self.price is not None:
            lines.append(f"Price: {self.price}")
        if self.candle_ts is not None:
            dt = datetime.fromtimestamp(self.candle_ts / 1000, tz=timezone.utc)
            lines.append(f"Candle: {dt.strftime('%Y-%m-%d %H:%M UTC')}")
        return "\n".join(lines)


def format_signals_digest(signals: list[Signal], *, title: str | None = None) -> str:
    if not signals:
        return ""
    if len(signals) == 1:
        return signals[0].format_message()

    header = title or f"Catch-up: {len(signals)} signals"
    blocks = [f"<b>{header}</b>"]
    for signal_item in signals:
        blocks.append(signal_item.format_message())
    return "\n\n".join(blocks)
