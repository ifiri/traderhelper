from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from traderhelper.market import Candle, parse_okx_candle_row

logger = logging.getLogger(__name__)

REST_BASE = "https://www.okx.com"
MAX_CANDLE_PAGES = 20
REST_MAX_ATTEMPTS = 5
REST_RETRY_BASE_DELAY = 0.5


class OkxRestClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str = REST_BASE,
        *,
        max_attempts: int = REST_MAX_ATTEMPTS,
        retry_base_delay: float = REST_RETRY_BASE_DELAY,
        verbose: bool = False,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max_attempts
        self._retry_base_delay = retry_base_delay
        self._verbose = verbose

    async def fetch_candles(
        self,
        inst_id: str,
        bar: str,
        limit: int = 200,
        after: str | None = None,
    ) -> list[Candle]:
        params: dict[str, str] = {
            "instId": inst_id,
            "bar": bar,
            "limit": str(min(limit, 300)),
        }
        if after is not None:
            params["after"] = after

        url = f"{self._base_url}/api/v5/market/candles"
        payload = await self._request_json(url, params)
        if payload.get("code") != "0":
            raise RuntimeError(
                f"OKX candles error for {inst_id} {bar}: "
                f"{payload.get('code')} {payload.get('msg')}"
            )

        rows = payload.get("data") or []
        candles = [parse_okx_candle_row(row) for row in rows]
        candles.sort(key=lambda item: item.ts)
        logger.debug("fetched %s candles for %s %s", len(candles), inst_id, bar)
        return candles

    async def fetch_candles_since(
        self,
        inst_id: str,
        bar: str,
        since_ts: int,
        page_size: int = 300,
    ) -> list[Candle]:
        collected: dict[int, Candle] = {}
        after: str | None = None
        limit = min(page_size, 300)

        for page in range(MAX_CANDLE_PAGES):
            batch = await self.fetch_candles(inst_id, bar, limit=limit, after=after)
            if not batch:
                break

            for candle in batch:
                if candle.ts >= since_ts:
                    collected[candle.ts] = candle

            oldest_ts = batch[0].ts
            if oldest_ts <= since_ts or len(batch) < limit:
                break

            next_after = str(oldest_ts)
            if after == next_after:
                break
            after = next_after
            logger.debug(
                "paging candles for %s %s page=%s oldest_ts=%s",
                inst_id,
                bar,
                page + 1,
                oldest_ts,
            )
        else:
            logger.warning(
                "candle gap fill hit page limit (%s) for %s %s since_ts=%s collected=%s",
                MAX_CANDLE_PAGES,
                inst_id,
                bar,
                since_ts,
                len(collected),
            )

        candles = sorted(collected.values(), key=lambda item: item.ts)
        logger.debug(
            "fetched %s candles since %s for %s %s",
            len(candles),
            since_ts,
            inst_id,
            bar,
        )
        return candles

    async def _request_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                async with self._session.get(url, params=params) as response:
                    if response.status == 429:
                        delay = self._retry_delay(attempt, response.headers.get("Retry-After"))
                        logger.warning(
                            "OKX rate limited (429), attempt %s/%s, sleep %.1fs",
                            attempt,
                            self._max_attempts,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    if response.status >= 500:
                        delay = self._retry_delay(attempt, None)
                        body = await response.text()
                        logger.warning(
                            "OKX server error %s, attempt %s/%s, sleep %.1fs: %s",
                            response.status,
                            attempt,
                            self._max_attempts,
                            delay,
                            body[:200],
                        )
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    payload: dict[str, Any] = await response.json()
                    if self._verbose:
                        logger.info(
                            "OKX REST %s params=%s status=%s body=%s",
                            url,
                            params,
                            response.status,
                            json.dumps(payload, ensure_ascii=False),
                        )
                    return payload
            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                last_error = error
                if attempt >= self._max_attempts:
                    break
                delay = self._retry_delay(attempt, None)
                logger.warning(
                    "OKX request failed attempt %s/%s: %s; retry in %.1fs",
                    attempt,
                    self._max_attempts,
                    error,
                    delay,
                )
                await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"OKX request failed after {self._max_attempts} attempts: {url}")

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return max(float(retry_after), self._retry_base_delay)
            except ValueError:
                pass
        return self._retry_base_delay * (2 ** (attempt - 1))
