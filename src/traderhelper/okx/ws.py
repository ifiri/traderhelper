from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from traderhelper.config import WatchConfig, candle_channel, watch_key
from traderhelper.market import Candle, parse_okx_candle_row

logger = logging.getLogger(__name__)

WS_BUSINESS = "wss://ws.okx.com:8443/ws/v5/business"
_EXPECTED_DISCONNECT = (
    ConnectionClosed,
    ConnectionResetError,
    ConnectionAbortedError,
    TimeoutError,
    asyncio.TimeoutError,
)


@dataclass(slots=True, frozen=True)
class CandleUpdate:
    key: str
    inst_id: str
    timeframe: str
    candle: Candle


OnCandle = Callable[[CandleUpdate], Awaitable[None]]
OnReconnect = Callable[[], Awaitable[None]]


class OkxCandleStream:
    def __init__(
        self,
        watches: Sequence[WatchConfig],
        on_candle: OnCandle,
        on_reconnect: OnReconnect | None = None,
        url: str = WS_BUSINESS,
        ping_interval: float = 20.0,
        reconnect_delay: float = 3.0,
        max_reconnect_delay: float = 60.0,
        verbose: bool = False,
    ) -> None:
        self._watches = list(watches)
        self._on_candle = on_candle
        self._on_reconnect = on_reconnect
        self._url = url
        self._ping_interval = ping_interval
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._verbose = verbose
        self._stop = asyncio.Event()
        self._first_connect = True

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        delay = self._reconnect_delay
        while not self._stop.is_set():
            failed = False
            try:
                await self._session_loop()
            except asyncio.CancelledError:
                raise
            except _EXPECTED_DISCONNECT as error:
                logger.warning("OKX websocket disconnected: %s", error)
            except OSError as error:
                failed = True
                logger.warning("OKX websocket network error: %s", error)
            except Exception:
                failed = True
                logger.exception("OKX websocket session failed")
            if self._stop.is_set():
                break
            logger.info("reconnecting OKX websocket in %.1fs", delay)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            if failed:
                delay = min(delay * 2, self._max_reconnect_delay)
            else:
                delay = self._reconnect_delay

    async def _session_loop(self) -> None:
        logger.info("connecting to %s", self._url)
        async with websockets.connect(
            self._url,
            ping_interval=None,
            close_timeout=5,
            max_queue=1024,
        ) as ws:
            await self._subscribe(ws)
            if not self._first_connect and self._on_reconnect is not None:
                await self._on_reconnect()
            self._first_connect = False
            await self._read_loop(ws)

    async def _subscribe(self, ws: ClientConnection) -> None:
        args = [
            {"channel": candle_channel(watch.timeframe), "instId": watch.inst_id}
            for watch in self._watches
        ]
        payload = {"op": "subscribe", "args": args}
        await ws.send(json.dumps(payload))
        logger.info("subscribed to %s candle channels", len(args))

    async def _read_loop(self, ws: ClientConnection) -> None:
        ping_task = asyncio.create_task(self._ping_loop(ws))
        try:
            while not self._stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=self._ping_interval * 2)
                except asyncio.TimeoutError:
                    logger.warning("OKX websocket idle timeout")
                    break
                if raw == "pong":
                    continue
                await self._handle_message(raw)
        finally:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass

    async def _ping_loop(self, ws: ClientConnection) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(self._ping_interval)
            try:
                await ws.send("ping")
            except Exception:
                return

    async def _handle_message(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if raw == "pong":
            return

        if self._verbose:
            logger.info("OKX WS message: %s", raw if isinstance(raw, str) else raw)

        try:
            message: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("non-json OKX message: %s", raw[:200])
            return

        event = message.get("event")
        if event == "subscribe":
            logger.debug("subscribe ack: %s", message.get("arg"))
            return
        if event == "error":
            raise RuntimeError(f"OKX ws error: {message}")
        if event:
            return

        arg = message.get("arg") or {}
        channel = arg.get("channel") or ""
        inst_id_raw = arg.get("instId")
        data = message.get("data") or []
        if not channel.startswith("candle") or not inst_id_raw or not data:
            return

        inst_id = str(inst_id_raw).strip().upper()
        timeframe = channel.removeprefix("candle")
        key = watch_key(inst_id, timeframe)
        for row in data:
            try:
                candle = parse_okx_candle_row(row)
            except (TypeError, ValueError, IndexError) as error:
                logger.warning("skip bad OKX candle row for %s: %s (%s)", key, row, error)
                continue
            await self._on_candle(
                CandleUpdate(
                    key=key,
                    inst_id=inst_id,
                    timeframe=timeframe,
                    candle=candle,
                )
            )
