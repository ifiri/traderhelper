from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from traderhelper.okx.rest import OkxRestClient


def _response(*, status: int, payload: dict | None = None, headers: dict | None = None):
    response = MagicMock()
    response.status = status
    response.headers = headers or {}
    response.text = AsyncMock(return_value="error")
    response.json = AsyncMock(return_value=payload or {})
    response.raise_for_status = MagicMock()
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


@pytest.mark.asyncio
async def test_fetch_candles_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("traderhelper.okx.rest.asyncio.sleep", fake_sleep)

    session = MagicMock()
    limited = _response(status=429, headers={"Retry-After": "1.5"})
    ok = _response(
        status=200,
        payload={
            "code": "0",
            "data": [["1700000000000", "1", "2", "0.5", "1.5", "10", "10", "10", "1"]],
        },
    )
    session.get = MagicMock(side_effect=[limited, ok])

    client = OkxRestClient(session, max_attempts=3, retry_base_delay=0.5)
    candles = await client.fetch_candles("BTC-USDT", "1H", limit=1)

    assert len(candles) == 1
    assert candles[0].close == 1.5
    assert sleeps == [1.5]
    assert session.get.call_count == 2
