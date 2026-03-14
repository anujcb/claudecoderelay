"""Send-only Telegram client using OpenClaw's existing bot. No polling."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger("claudecoderelay.telegram")


class TelegramSender:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._client: Optional[httpx.AsyncClient] = None

    async def init(self):
        self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def send(self, text: str, parse_mode: str = "HTML") -> Optional[int]:
        """Send a message to Telegram. Returns the message_id on success."""
        try:
            resp = await self._client.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
            data = resp.json()
            if data.get("ok"):
                msg_id = data["result"]["message_id"]
                logger.info("Telegram message sent (id=%d)", msg_id)
                return msg_id
            else:
                logger.error("Telegram API error: %s", data.get("description"))
                return None
        except Exception:
            logger.exception("Failed to send Telegram message")
            return None
