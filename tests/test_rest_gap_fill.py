from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from helpers import make_candle
from traderhelper.okx.rest import OkxRestClient


@pytest.mark.asyncio
async def test_fetch_candles_since_paginates_until_since_ts() -> None:
    client = OkxRestClient(session=MagicMock())
    page_newer = [make_candle(ts, float(ts)) for ts in (300, 400, 500)]
    page_older = [make_candle(ts, float(ts)) for ts in (100, 200, 300)]
    client.fetch_candles = AsyncMock(side_effect=[page_newer, page_older])

    candles = await client.fetch_candles_since(
        "BTC-USDT",
        "1m",
        since_ts=150,
        page_size=3,
    )

    assert [candle.ts for candle in candles] == [200, 300, 400, 500]
    assert client.fetch_candles.await_count == 2
    second_call = client.fetch_candles.await_args_list[1]
    assert second_call.kwargs["after"] == "300"


@pytest.mark.asyncio
async def test_fetch_candles_since_stops_when_page_covers_since() -> None:
    client = OkxRestClient(session=MagicMock())
    page = [make_candle(ts, float(ts)) for ts in (100, 200, 300)]
    client.fetch_candles = AsyncMock(return_value=page)

    candles = await client.fetch_candles_since(
        "BTC-USDT",
        "1m",
        since_ts=150,
        page_size=3,
    )

    assert [candle.ts for candle in candles] == [200, 300]
    assert client.fetch_candles.await_count == 1
