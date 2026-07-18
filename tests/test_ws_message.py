from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from traderhelper.okx.ws import OkxCandleStream


@pytest.mark.asyncio
async def test_handle_message_normalizes_inst_id_and_skips_bad_rows() -> None:
    on_candle = AsyncMock()
    stream = OkxCandleStream(watches=[], on_candle=on_candle)
    payload = {
        "arg": {"channel": "candle1H", "instId": "btc-usdt"},
        "data": [
            ["bad"],
            ["1700000000000", "1", "2", "0.5", "1.5", "10", "10", "10", "1"],
        ],
    }

    await stream._handle_message(json.dumps(payload))

    assert on_candle.await_count == 1
    update = on_candle.await_args.args[0]
    assert update.inst_id == "BTC-USDT"
    assert update.key == "BTC-USDT:1H"
    assert update.candle.close == 1.5


@pytest.mark.asyncio
async def test_handle_message_error_event_raises() -> None:
    stream = OkxCandleStream(watches=[], on_candle=AsyncMock())
    with pytest.raises(RuntimeError, match="OKX ws error"):
        await stream._handle_message(json.dumps({"event": "error", "msg": "boom"}))
