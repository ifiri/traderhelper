from __future__ import annotations

from collections import OrderedDict

from traderhelper.market import Candle


class CandleStore:
    def __init__(self, max_candles: int = 300) -> None:
        self._max_candles = max_candles
        self._series: dict[str, OrderedDict[int, Candle]] = {}
        self._live: dict[str, Candle] = {}

    def seed(self, key: str, candles: list[Candle]) -> None:
        ordered: OrderedDict[int, Candle] = OrderedDict()
        for candle in sorted(candles, key=lambda item: item.ts):
            if candle.confirm:
                ordered[candle.ts] = candle
        while len(ordered) > self._max_candles:
            ordered.popitem(last=False)
        self._series[key] = ordered
        self._live.pop(key, None)

    def upsert(self, key: str, candle: Candle) -> Candle | None:
        if not candle.confirm:
            self._live[key] = candle
            return None

        series = self._series.setdefault(key, OrderedDict())
        previous = series.get(candle.ts)
        self._put_closed(series, candle)
        self._series[key] = series
        self._trim(series)

        live = self._live.get(key)
        if live is not None and live.ts <= candle.ts:
            self._live.pop(key, None)

        if previous is None or not previous.confirm:
            return candle
        return None

    def closed_candles(self, key: str) -> list[Candle]:
        series = self._series.get(key, OrderedDict())
        return list(series.values())

    def last_price(self, key: str) -> float | None:
        live = self._live.get(key)
        if live is not None:
            return live.close
        series = self._series.get(key)
        if not series:
            return None
        return next(reversed(series.values())).close

    def latest_closed_ts(self, key: str) -> int | None:
        series = self._series.get(key)
        if not series:
            return None
        return next(reversed(series.values())).ts

    def _put_closed(self, series: OrderedDict[int, Candle], candle: Candle) -> None:
        if candle.ts in series:
            series[candle.ts] = candle
            return

        if not series or candle.ts > next(reversed(series)):
            series[candle.ts] = candle
            return

        series[candle.ts] = candle
        rebuilt = OrderedDict(sorted(series.items(), key=lambda item: item[0]))
        series.clear()
        series.update(rebuilt)

    def _trim(self, series: OrderedDict[int, Candle]) -> None:
        while len(series) > self._max_candles:
            series.popitem(last=False)
