from __future__ import annotations

from helpers import make_candle
from traderhelper.market.candle_store import CandleStore


def test_seed_keeps_only_confirmed() -> None:
    store = CandleStore(max_candles=10)
    store.seed(
        "BTC:1H",
        [
            make_candle(1, 1.0, confirm=True),
            make_candle(2, 2.0, confirm=False),
            make_candle(3, 3.0, confirm=True),
        ],
    )
    closed = store.closed_candles("BTC:1H")
    assert [candle.ts for candle in closed] == [1, 3]


def test_live_candle_does_not_evict_history() -> None:
    store = CandleStore(max_candles=2)
    store.seed(
        "BTC:1H",
        [make_candle(1, 1.0), make_candle(2, 2.0)],
    )
    assert store.upsert("BTC:1H", make_candle(3, 3.0, confirm=False)) is None
    assert [candle.ts for candle in store.closed_candles("BTC:1H")] == [1, 2]
    assert store.last_price("BTC:1H") == 3.0


def test_upsert_returns_only_first_confirm() -> None:
    store = CandleStore(max_candles=10)
    first = make_candle(1, 1.0, confirm=True)
    assert store.upsert("BTC:1H", first) == first
    assert store.upsert("BTC:1H", make_candle(1, 1.1, confirm=True)) is None


def test_confirm_clears_older_live() -> None:
    store = CandleStore(max_candles=10)
    store.upsert("BTC:1H", make_candle(1, 1.0, confirm=False))
    store.upsert("BTC:1H", make_candle(1, 1.0, confirm=True))
    assert store.last_price("BTC:1H") == 1.0
    assert store.latest_closed_ts("BTC:1H") == 1
