from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


OKX_TIMEFRAMES = frozenset(
    {
        "1s",
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1H",
        "2H",
        "4H",
        "6H",
        "12H",
        "1D",
        "2D",
        "3D",
        "5D",
        "1W",
        "1M",
        "3M",
    }
)


class PriceAlertType(str, Enum):
    ABOVE = "above"
    BELOW = "below"


class ComboConditionKind(str, Enum):
    RSI = "rsi"
    EMA_CROSS = "ema_cross"
    MACD_CROSS = "macd_cross"
    DIVERGENCE = "divergence"


class ComboDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class PriceAlertConfig(BaseModel):
    type: PriceAlertType
    value: float = Field(gt=0)


class RsiConfig(BaseModel):
    period: int = Field(default=14, ge=2)
    overbought: float = Field(default=70, gt=0, le=100)
    oversold: float = Field(default=30, ge=0, lt=100)

    @model_validator(mode="after")
    def overbought_above_oversold(self) -> RsiConfig:
        if self.overbought <= self.oversold:
            raise ValueError("overbought must be greater than oversold")
        return self


class DivergenceConfig(BaseModel):
    rsi: bool = False
    macd: bool = False
    lookback: int = Field(default=60, ge=10)
    pivot_left: int = Field(default=3, ge=1)
    pivot_right: int = Field(default=3, ge=1)


class EmaConfig(BaseModel):
    fast: int = Field(default=20, ge=2)
    mid: int = Field(default=100, ge=2)
    slow: int = Field(default=200, ge=3)
    cross: bool = True

    @model_validator(mode="after")
    def periods_ordered(self) -> EmaConfig:
        if self.fast >= self.slow:
            raise ValueError("ema fast must be less than slow")
        if self.mid <= self.fast or self.mid >= self.slow:
            raise ValueError("ema mid must be between fast and slow")
        return self


class ComboCondition(BaseModel):
    kind: ComboConditionKind
    direction: ComboDirection


class ComboRuleConfig(BaseModel):
    name: str = Field(min_length=1)
    window: int = Field(default=10, ge=2)
    require: list[ComboCondition] = Field(min_length=2)


class WatchConfig(BaseModel):
    inst_id: str
    timeframe: str
    price_alerts: list[PriceAlertConfig] = Field(default_factory=list)
    macd_cross: bool = False
    rsi: RsiConfig | None = None
    ema: EmaConfig | None = None
    divergence: DivergenceConfig | None = None
    combo: list[ComboRuleConfig] = Field(default_factory=list)
    macd_fast: int = Field(default=12, ge=2)
    macd_slow: int = Field(default=26, ge=3)
    macd_signal: int = Field(default=9, ge=2)

    @field_validator("inst_id")
    @classmethod
    def normalize_inst_id(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        if value not in OKX_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {value}")
        return value

    @model_validator(mode="after")
    def macd_slow_above_fast(self) -> WatchConfig:
        if self.macd_slow <= self.macd_fast:
            raise ValueError("macd_slow must be greater than macd_fast")
        return self

    @model_validator(mode="after")
    def at_least_one_signal(self) -> WatchConfig:
        divergence_enabled = self.divergence is not None and (
            self.divergence.rsi or self.divergence.macd
        )
        ema_enabled = self.ema is not None and self.ema.cross
        if (
            not self.price_alerts
            and not self.macd_cross
            and self.rsi is None
            and not divergence_enabled
            and not ema_enabled
            and not self.combo
        ):
            raise ValueError(
                f"watch {self.inst_id}:{self.timeframe} has no enabled signals"
            )
        return self

    def combo_requires(self, kind: ComboConditionKind) -> bool:
        return any(
            condition.kind == kind for rule in self.combo for condition in rule.require
        )

    def effective_rsi(self) -> RsiConfig:
        return self.rsi if self.rsi is not None else RsiConfig()

    def effective_ema(self) -> EmaConfig:
        return self.ema if self.ema is not None else EmaConfig(cross=False)

    def effective_divergence(self) -> DivergenceConfig | None:
        if self.divergence is not None:
            return self.divergence
        if self.combo_requires(ComboConditionKind.DIVERGENCE):
            return DivergenceConfig(rsi=True, macd=True)
        return None


class AppConfig(BaseModel):
    watches: list[WatchConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_watch_keys(self) -> AppConfig:
        seen: set[str] = set()
        for watch in self.watches:
            key = watch_key(watch.inst_id, watch.timeframe)
            if key in seen:
                raise ValueError(f"duplicate watch: {key}")
            seen.add(key)
        return self


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str
    telegram_chat_id: str


def load_config(
    config_path: str | Path = "config.yaml",
    env_path: str | Path | None = ".env",
) -> tuple[AppConfig, EnvSettings]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path.resolve()}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config must be a YAML mapping")

    app = AppConfig.model_validate(raw)
    if env_path is not None:
        load_dotenv(env_path)
        env = EnvSettings(_env_file=str(env_path))
    else:
        env = EnvSettings()
    return app, env


def candle_channel(timeframe: str) -> str:
    return f"candle{timeframe}"


def watch_key(inst_id: str, timeframe: str) -> str:
    return f"{inst_id}:{timeframe}"
