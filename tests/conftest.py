from __future__ import annotations

import pytest

from traderhelper.config import (
    DivergenceConfig,
    PriceAlertConfig,
    PriceAlertType,
    RsiConfig,
    WatchConfig,
)


@pytest.fixture
def watch_macd() -> WatchConfig:
    return WatchConfig(inst_id="BTC-USDT", timeframe="1H", macd_cross=True)


@pytest.fixture
def watch_rsi() -> WatchConfig:
    return WatchConfig(
        inst_id="BTC-USDT",
        timeframe="1H",
        rsi=RsiConfig(period=14, overbought=70, oversold=30),
    )


@pytest.fixture
def watch_price() -> WatchConfig:
    return WatchConfig(
        inst_id="BTC-USDT",
        timeframe="1H",
        price_alerts=[
            PriceAlertConfig(type=PriceAlertType.ABOVE, value=100.0),
            PriceAlertConfig(type=PriceAlertType.BELOW, value=90.0),
        ],
    )


@pytest.fixture
def watch_divergence() -> WatchConfig:
    return WatchConfig(
        inst_id="BTC-USDT",
        timeframe="1H",
        divergence=DivergenceConfig(
            rsi=True,
            macd=False,
            lookback=60,
            pivot_left=1,
            pivot_right=1,
        ),
    )
