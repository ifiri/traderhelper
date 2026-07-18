from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from traderhelper.notify.telegram import TelegramNotifier


@pytest.mark.asyncio
async def test_ping_from_allowed_chat_replies_pong() -> None:
    notifier = TelegramNotifier(
        session=MagicMock(),
        bot_token="token",
        chat_id="123",
    )
    notifier.send = AsyncMock()

    await notifier._handle_update(
        {
            "update_id": 1,
            "message": {"chat": {"id": 123}, "text": "Ping"},
        }
    )

    notifier.send.assert_awaited_once_with("pong", chat_id="123", parse_mode=None)


@pytest.mark.asyncio
async def test_ping_from_other_chat_ignored() -> None:
    notifier = TelegramNotifier(
        session=MagicMock(),
        bot_token="token",
        chat_id="123",
    )
    notifier.send = AsyncMock()

    await notifier._handle_update(
        {
            "update_id": 1,
            "message": {"chat": {"id": 999}, "text": "ping"},
        }
    )

    notifier.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_ping_with_bot_username_suffix() -> None:
    notifier = TelegramNotifier(
        session=MagicMock(),
        bot_token="token",
        chat_id="123",
    )
    notifier.send = AsyncMock()

    await notifier._handle_update(
        {
            "update_id": 1,
            "message": {"chat": {"id": 123}, "text": "/ping@MyBot"},
        }
    )

    notifier.send.assert_awaited_once_with("pong", chat_id="123", parse_mode=None)
