from __future__ import annotations

from traderhelper.config import PriceAlertType, WatchConfig, watch_key
from traderhelper.signals import Signal, SignalKind
from traderhelper.signals.dedup import DedupState


def arm_price_alerts(watch: WatchConfig, price: float, state: DedupState) -> None:
    base = watch_key(watch.inst_id, watch.timeframe)
    for index, alert in enumerate(watch.price_alerts):
        key = f"{base}:price:{index}:{alert.type.value}:armed"
        if alert.type is PriceAlertType.ABOVE:
            state.set_armed(key, price < alert.value)
        else:
            state.set_armed(key, price > alert.value)


def detect_price_alerts(
    watch: WatchConfig,
    price: float,
    state: DedupState,
) -> list[Signal]:
    signals: list[Signal] = []
    base = watch_key(watch.inst_id, watch.timeframe)

    for index, alert in enumerate(watch.price_alerts):
        key = f"{base}:price:{index}:{alert.type.value}"
        armed_key = f"{key}:armed"

        if alert.type is PriceAlertType.ABOVE:
            crossed = price >= alert.value
            reset = price < alert.value
            direction = "above"
            title = "Price above threshold"
            body = f"Price {price} >= {alert.value}"
        else:
            crossed = price <= alert.value
            reset = price > alert.value
            direction = "below"
            title = "Price below threshold"
            body = f"Price {price} <= {alert.value}"

        if reset:
            state.set_armed(armed_key, True)
            continue
        if crossed and state.is_armed(armed_key):
            state.set_armed(armed_key, False)
            signals.append(
                Signal(
                    kind=SignalKind.PRICE,
                    inst_id=watch.inst_id,
                    timeframe=watch.timeframe,
                    direction=direction,
                    title=title,
                    body=body,
                    price=price,
                )
            )
        elif crossed:
            state.set_armed(armed_key, False)

    return signals
