from __future__ import annotations

import pytest
from pydantic import ValidationError

from traderhelper.config import (
    AppConfig,
    ComboCondition,
    ComboConditionKind,
    ComboDirection,
    ComboRuleConfig,
    DivergenceConfig,
    EmaConfig,
    WatchConfig,
)


def test_watch_requires_at_least_one_signal() -> None:
    with pytest.raises(ValidationError, match="no enabled signals"):
        WatchConfig(inst_id="BTC-USDT", timeframe="1H")


def test_divergence_both_disabled_is_not_a_signal() -> None:
    with pytest.raises(ValidationError, match="no enabled signals"):
        WatchConfig(
            inst_id="BTC-USDT",
            timeframe="1H",
            divergence=DivergenceConfig(rsi=False, macd=False),
        )


def test_app_rejects_duplicate_watches() -> None:
    with pytest.raises(ValidationError, match="duplicate watch"):
        AppConfig.model_validate(
            {
                "watches": [
                    {"inst_id": "BTC-USDT", "timeframe": "1H", "macd_cross": True},
                    {"inst_id": "btc-usdt", "timeframe": "1H", "macd_cross": True},
                ],
            }
        )


def test_ema_and_combo_count_as_signals() -> None:
    WatchConfig(inst_id="BTC-USDT", timeframe="1H", ema=EmaConfig(cross=True))
    WatchConfig(
        inst_id="BTC-USDT",
        timeframe="1H",
        combo=[
            ComboRuleConfig(
                name="test",
                window=5,
                require=[
                    ComboCondition(
                        kind=ComboConditionKind.RSI,
                        direction=ComboDirection.BULLISH,
                    ),
                    ComboCondition(
                        kind=ComboConditionKind.EMA_CROSS,
                        direction=ComboDirection.BULLISH,
                    ),
                ],
            )
        ],
    )


def test_combo_requires_at_least_two_conditions() -> None:
    with pytest.raises(ValidationError):
        ComboRuleConfig(
            name="bad",
            require=[
                ComboCondition(
                    kind=ComboConditionKind.RSI,
                    direction=ComboDirection.BULLISH,
                )
            ],
        )
