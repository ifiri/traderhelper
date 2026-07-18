from __future__ import annotations

import pytest

from traderhelper.market import parse_okx_candle_row


def test_parse_okx_candle_row_confirmed() -> None:
    candle = parse_okx_candle_row(
        ["1700000000000", "1", "2", "0.5", "1.5", "10", "10", "10", "1"]
    )
    assert candle.ts == 1700000000000
    assert candle.open == 1.0
    assert candle.high == 2.0
    assert candle.low == 0.5
    assert candle.close == 1.5
    assert candle.volume == 10.0
    assert candle.confirm is True


def test_parse_okx_candle_row_unconfirmed() -> None:
    candle = parse_okx_candle_row(
        ["1700000000000", "1", "2", "0.5", "1.5", "10", "10", "10", "0"]
    )
    assert candle.confirm is False


def test_parse_okx_candle_row_rejects_short_row() -> None:
    with pytest.raises(ValueError, match="too short"):
        parse_okx_candle_row(["1700000000000", "1", "2", "0.5", "1.5", "10"])
