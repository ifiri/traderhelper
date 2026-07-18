from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from pathlib import Path

import aiohttp

from traderhelper.config import AppConfig, EnvSettings, WatchConfig, load_config, watch_key
from traderhelper.indicators import IndicatorSnapshot, compute_indicators
from traderhelper.market import Candle
from traderhelper.market.candle_store import CandleStore
from traderhelper.notify import TelegramNotifier
from traderhelper.okx import CandleUpdate, OkxCandleStream, OkxRestClient
from traderhelper.signals import Signal
from traderhelper.signals.combo import detect_combo
from traderhelper.signals.conditions import ConditionTracker, update_conditions
from traderhelper.signals.dedup import DedupState
from traderhelper.signals.divergence import detect_divergences
from traderhelper.signals.ema_cross import detect_ema_cross
from traderhelper.signals.macd_cross import detect_macd_cross
from traderhelper.signals.price import arm_price_alerts, detect_price_alerts
from traderhelper.signals.rsi import arm_rsi_levels, detect_rsi_levels

logger = logging.getLogger(__name__)

WARMUP_CONCURRENCY = 5
DEFAULT_HISTORY_LIMIT = 300


class SignalDaemon:
    def __init__(
        self,
        app: AppConfig,
        env: EnvSettings,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
        *,
        verbose: bool = False,
    ) -> None:
        self._app = app
        self._env = env
        self._history_limit = history_limit
        self._verbose = verbose
        self._store = CandleStore(max_candles=max(history_limit + 50, 350))
        self._state = DedupState()
        self._conditions = ConditionTracker()
        self._watches: dict[str, WatchConfig] = {
            watch_key(watch.inst_id, watch.timeframe): watch for watch in app.watches
        }
        self._session: aiohttp.ClientSession | None = None
        self._rest: OkxRestClient | None = None
        self._notifier: TelegramNotifier | None = None
        self._stream: OkxCandleStream | None = None
        self._warmup_done = False

    async def run(self) -> None:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self._session = session
            self._rest = OkxRestClient(session, verbose=self._verbose)
            self._notifier = TelegramNotifier(
                session,
                bot_token=self._env.telegram_bot_token,
                chat_id=self._env.telegram_chat_id,
                verbose=self._verbose,
            )
            poll_task = asyncio.create_task(self._notifier.run_poll_loop())
            try:
                await self._warmup()
                self._warmup_done = True
                self._stream = OkxCandleStream(
                    watches=self._app.watches,
                    on_candle=self._on_candle,
                    on_reconnect=self._on_reconnect,
                    verbose=self._verbose,
                )
                await self._stream.run()
            finally:
                self._notifier.stop()
                poll_task.cancel()
                try:
                    await poll_task
                except asyncio.CancelledError:
                    pass

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
        if self._notifier is not None:
            self._notifier.stop()

    async def _warmup(self) -> None:
        assert self._rest is not None
        semaphore = asyncio.Semaphore(WARMUP_CONCURRENCY)

        async def warm_one(watch: WatchConfig) -> None:
            assert self._rest is not None
            async with semaphore:
                key = watch_key(watch.inst_id, watch.timeframe)
                candles = await self._rest.fetch_candles(
                    watch.inst_id,
                    watch.timeframe,
                    limit=self._history_limit,
                )
                self._store.seed(key, candles)
                closed = self._store.closed_candles(key)
                logger.info("warmed %s with %s closed candles", key, len(closed))
                price = self._store.last_price(key)
                if price is not None:
                    arm_price_alerts(watch, price, self._state)
                snapshot = self._compute_snapshot(watch, closed)
                if snapshot is not None:
                    arm_rsi_levels(watch, snapshot, self._state)
                    update_conditions(watch, closed, snapshot, self._conditions)
                    detect_macd_cross(watch, closed, snapshot, self._state)
                    detect_ema_cross(watch, closed, snapshot, self._state)
                    detect_divergences(watch, closed, snapshot, self._state)
                    detect_combo(watch, closed, self._conditions, self._state)

        await asyncio.gather(*(warm_one(watch) for watch in self._app.watches))

    async def _on_reconnect(self) -> None:
        assert self._rest is not None
        logger.info("refilling candle gaps after reconnect")
        catch_up_signals = 0
        for watch in self._app.watches:
            key = watch_key(watch.inst_id, watch.timeframe)
            latest = self._store.latest_closed_ts(key)
            if latest is None:
                candles = await self._rest.fetch_candles(
                    watch.inst_id,
                    watch.timeframe,
                    limit=self._history_limit,
                )
                self._store.seed(key, candles)
                continue
            candles = await self._rest.fetch_candles_since(
                watch.inst_id,
                watch.timeframe,
                since_ts=latest,
            )
            for candle in candles:
                if not candle.confirm:
                    continue
                closed = self._store.upsert(key, candle)
                if closed is not None and self._warmup_done:
                    catch_up_signals += await self._process_closed(watch, emit=True)
        logger.info("reconnect catch-up emitted %s signals", catch_up_signals)

    async def _on_candle(self, update: CandleUpdate) -> None:
        watch = self._watches.get(update.key)
        if watch is None:
            return

        closed = self._store.upsert(update.key, update.candle)
        price = update.candle.close
        await self._emit_signals(detect_price_alerts(watch, price, self._state))

        if closed is not None:
            await self._process_closed(watch, emit=True)

    def _compute_snapshot(
        self,
        watch: WatchConfig,
        candles: list[Candle],
    ) -> IndicatorSnapshot | None:
        rsi_period = watch.effective_rsi().period
        ema = watch.effective_ema()
        return compute_indicators(
            candles,
            rsi_period=rsi_period,
            macd_fast=watch.macd_fast,
            macd_slow=watch.macd_slow,
            macd_signal=watch.macd_signal,
            ema_fast=ema.fast,
            ema_mid=ema.mid,
            ema_slow=ema.slow,
        )

    async def _process_closed(self, watch: WatchConfig, *, emit: bool) -> int:
        key = watch_key(watch.inst_id, watch.timeframe)
        candles = self._store.closed_candles(key)
        snapshot = self._compute_snapshot(watch, candles)
        if snapshot is None:
            logger.debug("not enough candles for indicators on %s", key)
            return 0

        update_conditions(watch, candles, snapshot, self._conditions)

        signals: list[Signal] = []
        signals.extend(detect_macd_cross(watch, candles, snapshot, self._state))
        signals.extend(detect_rsi_levels(watch, candles, snapshot, self._state))
        signals.extend(detect_ema_cross(watch, candles, snapshot, self._state))
        signals.extend(detect_divergences(watch, candles, snapshot, self._state))
        signals.extend(detect_combo(watch, candles, self._conditions, self._state))
        if emit:
            await self._emit_signals(signals)
            return len(signals)
        return 0

    async def _emit_signals(self, signals: list[Signal]) -> None:
        if not signals or self._notifier is None:
            return
        for signal_item in signals:
            logger.info(
                "signal %s %s %s %s",
                signal_item.kind.value,
                signal_item.inst_id,
                signal_item.timeframe,
                signal_item.direction,
            )
            try:
                await self._notifier.send(signal_item.format_message())
            except Exception:
                logger.exception("failed to send telegram signal")


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OKX signal daemon")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="path to YAML config",
    )
    parser.add_argument(
        "--env",
        default=".env",
        help="path to .env with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="debug logging and print OKX/Telegram API responses",
    )
    return parser


async def async_main(config_path: Path, env_path: Path, *, verbose: bool = False) -> None:
    app, env = load_config(config_path, env_path)
    daemon = SignalDaemon(app, env, verbose=verbose)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, daemon.stop)
        except NotImplementedError:
            pass

    await daemon.run()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.verbose)
    try:
        asyncio.run(
            async_main(Path(args.config), Path(args.env), verbose=args.verbose)
        )
    except KeyboardInterrupt:
        logger.info("stopped")


if __name__ == "__main__":
    main()
