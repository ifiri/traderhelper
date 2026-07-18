from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
POLL_TIMEOUT_SEC = 25


class TelegramTransientError(Exception):
    pass


class TelegramNotifier:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        bot_token: str,
        chat_id: str,
        *,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        verbose: bool = False,
    ) -> None:
        self._session = session
        self._bot_token = bot_token
        self._chat_id = str(chat_id).strip()
        self._base = f"{TELEGRAM_API}/bot{bot_token}"
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._verbose = verbose
        self._stop = asyncio.Event()
        self._offset = 0

    def stop(self) -> None:
        self._stop.set()

    async def send(
        self,
        text: str,
        *,
        chat_id: str | None = None,
        parse_mode: str | None = "HTML",
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id or self._chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
        url = f"{self._base}/sendMessage"
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                async with self._session.post(url, json=payload) as response:
                    body: dict[str, Any] = await response.json(content_type=None)
                    if self._verbose:
                        logger.info(
                            "Telegram sendMessage status=%s body=%s",
                            response.status,
                            json.dumps(body, ensure_ascii=False),
                        )
                    if response.status >= 400 or not body.get("ok"):
                        raise RuntimeError(f"Telegram send failed: {response.status} {body}")
                logger.info("telegram message sent")
                return
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as error:
                last_error = error
                if attempt >= self._max_attempts:
                    break
                delay = self._base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "telegram send attempt %s/%s failed: %s; retry in %.1fs",
                    attempt,
                    self._max_attempts,
                    error,
                    delay,
                )
                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error

    async def run_poll_loop(self) -> None:
        logger.info("telegram command poll starting for chat_id=%s", self._chat_id)
        await self._skip_pending_updates()
        logger.info("telegram command poll started (ping -> pong)")
        while not self._stop.is_set():
            try:
                updates = await self._get_updates(timeout=POLL_TIMEOUT_SEC)
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                logger.debug("telegram getUpdates timed out, retrying")
                continue
            except TelegramTransientError as error:
                logger.warning("telegram getUpdates temporary error: %s", error)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass
                continue
            except (aiohttp.ClientError, OSError) as error:
                logger.warning("telegram getUpdates network error: %s", error)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass
                continue
            except Exception:
                logger.exception("telegram getUpdates failed")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass
                continue

            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    self._offset = update_id + 1
                try:
                    await self._handle_update(update)
                except Exception:
                    logger.exception("telegram update handling failed")

    async def _skip_pending_updates(self) -> None:
        try:
            updates = await self._get_updates(timeout=0)
        except TelegramTransientError as error:
            logger.warning("skip pending telegram updates temporary error: %s", error)
            return
        except Exception:
            logger.exception("failed to skip pending telegram updates")
            return
        if updates:
            last_id = updates[-1].get("update_id")
            if isinstance(last_id, int):
                self._offset = last_id + 1
            logger.info("skipped %s pending telegram updates", len(updates))

    async def _get_updates(self, *, timeout: int) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": json.dumps(["message"]),
        }
        if self._offset > 0:
            params["offset"] = self._offset

        url = f"{self._base}/getUpdates"
        sock_read = float(timeout + 15) if timeout > 0 else 30.0
        request_timeout = aiohttp.ClientTimeout(
            total=None,
            sock_connect=15,
            sock_read=sock_read,
        )
        async with self._session.get(url, params=params, timeout=request_timeout) as response:
            body: dict[str, Any] = await response.json(content_type=None)
            if self._verbose:
                logger.info(
                    "Telegram getUpdates status=%s body=%s",
                    response.status,
                    json.dumps(body, ensure_ascii=False),
                )
            if response.status == 429 or response.status >= 500:
                raise TelegramTransientError(f"{response.status} {body}")
            error_code = body.get("error_code")
            if not body.get("ok"):
                if error_code == 429 or (isinstance(error_code, int) and error_code >= 500):
                    raise TelegramTransientError(f"{response.status} {body}")
                raise RuntimeError(f"Telegram getUpdates failed: {response.status} {body}")
            if response.status >= 400:
                raise RuntimeError(f"Telegram getUpdates failed: {response.status} {body}")
            result = body.get("result") or []
            return result if isinstance(result, list) else []

    @staticmethod
    def _normalize_command(text: str) -> str:
        normalized = text.strip().lower()
        if normalized.startswith("/"):
            command = normalized[1:]
            return command.split("@", 1)[0]
        return normalized

    async def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", "")).strip()
        text = str(message.get("text") or "")
        if not text:
            return

        if chat_id != self._chat_id:
            logger.warning(
                "telegram message ignored: chat_id=%s expected=%s text=%r",
                chat_id,
                self._chat_id,
                text[:80],
            )
            return

        if self._normalize_command(text) == "ping":
            logger.info("telegram ping received from chat %s", chat_id)
            await self.send("pong", chat_id=chat_id, parse_mode=None)
