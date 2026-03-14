"""SQLite-backed question queue for Claude Code Relay."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from .models import Question

logger = logging.getLogger("claudecoderelay.queue")

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    short_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    hook_type TEXT,
    tool_name TEXT,
    tool_input TEXT,
    formatted_question TEXT,
    telegram_message_id INTEGER,
    timeout_seconds INTEGER DEFAULT 1800,
    status TEXT DEFAULT 'pending',
    reply TEXT,
    decision TEXT,
    replied_at TEXT
);
"""


class QueueManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(CREATE_TABLE)
        await self._db.commit()
        logger.info("Queue database initialised at %s", self.db_path)

    async def close(self):
        if self._db:
            await self._db.close()

    # ── Write ───────────────────────────────────────────────────────────────

    async def add_question(self, q: Question) -> Question:
        await self._db.execute(
            """INSERT INTO questions
               (id, short_id, created_at, hook_type, tool_name, tool_input,
                formatted_question, timeout_seconds, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                q.id, q.short_id, q.created_at, q.hook_type, q.tool_name,
                q.tool_input, q.formatted_question, q.timeout_seconds, q.status,
            ),
        )
        await self._db.commit()
        logger.info("Queued question %s [%s] %s %s", q.id, q.short_id, q.hook_type, q.tool_name)
        return q

    async def set_telegram_message_id(self, question_id: str, message_id: int):
        await self._db.execute(
            "UPDATE questions SET telegram_message_id = ? WHERE id = ?",
            (message_id, question_id),
        )
        await self._db.commit()

    async def store_reply(self, question_id: str, reply: str, decision: str, replied_at: str) -> bool:
        cursor = await self._db.execute(
            """UPDATE questions SET reply = ?, decision = ?, replied_at = ?, status = 'answered'
               WHERE id = ? AND status = 'pending'""",
            (reply, decision, replied_at, question_id),
        )
        await self._db.commit()
        changed = cursor.rowcount > 0
        if changed:
            logger.info("Reply stored for %s: %s (%s)", question_id, decision, reply)
        else:
            logger.warning("No pending question %s to store reply", question_id)
        return changed

    async def cancel_question(self, question_id: str) -> bool:
        cursor = await self._db.execute(
            """UPDATE questions SET status = 'cancelled'
               WHERE id = ? AND status = 'pending'""",
            (question_id,),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def cancel_all(self) -> int:
        cursor = await self._db.execute(
            "UPDATE questions SET status = 'cancelled' WHERE status = 'pending'"
        )
        await self._db.commit()
        return cursor.rowcount

    # ── Read ────────────────────────────────────────────────────────────────

    async def get_question(self, question_id: str) -> Optional[Question]:
        async with self._db.execute(
            "SELECT * FROM questions WHERE id = ? OR short_id = ?",
            (question_id, question_id),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_question(row) if row else None

    async def get_pending(self) -> list[Question]:
        async with self._db.execute(
            "SELECT * FROM questions WHERE status = 'pending' ORDER BY created_at ASC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_question(r) for r in rows]

    async def get_history(self, limit: int = 10) -> list[Question]:
        async with self._db.execute(
            "SELECT * FROM questions ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_question(r) for r in rows]

    # ── Expiry ──────────────────────────────────────────────────────────────

    async def expire_stale(self) -> list[Question]:
        """Find and expire stale questions. Returns the expired questions."""
        now = datetime.now(timezone.utc).isoformat()
        # First fetch them so we can notify
        async with self._db.execute(
            """SELECT * FROM questions
               WHERE status = 'pending'
               AND datetime(created_at, '+' || timeout_seconds || ' seconds') < datetime(?)""",
            (now,),
        ) as cursor:
            rows = await cursor.fetchall()
            expired = [self._row_to_question(r) for r in rows]

        if expired:
            await self._db.execute(
                """UPDATE questions SET status = 'expired'
                   WHERE status = 'pending'
                   AND datetime(created_at, '+' || timeout_seconds || ' seconds') < datetime(?)""",
                (now,),
            )
            await self._db.commit()
            logger.info("Expired %d stale questions", len(expired))

        return expired

    # ── Stats ───────────────────────────────────────────────────────────────

    async def stats(self) -> dict:
        counts = {}
        for status in ("pending", "answered", "expired", "cancelled"):
            async with self._db.execute(
                "SELECT COUNT(*) FROM questions WHERE status = ?", (status,)
            ) as cursor:
                row = await cursor.fetchone()
                counts[status] = row[0]

        # Last activity
        async with self._db.execute(
            "SELECT * FROM questions ORDER BY created_at DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                q = self._row_to_question(row)
                counts["last_activity"] = {
                    "id": q.short_id,
                    "status": q.status,
                    "question": q.formatted_question,
                    "created_at": q.created_at,
                    "decision": q.decision,
                }

        return counts

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_question(row) -> Question:
        return Question(
            id=row["id"],
            short_id=row["short_id"],
            created_at=row["created_at"],
            hook_type=row["hook_type"],
            tool_name=row["tool_name"],
            tool_input=row["tool_input"],
            formatted_question=row["formatted_question"],
            telegram_message_id=row["telegram_message_id"],
            timeout_seconds=row["timeout_seconds"],
            status=row["status"],
            reply=row["reply"],
            decision=row["decision"],
            replied_at=row["replied_at"],
        )


async def run_expiry_loop(queue: QueueManager, telegram_sender, config: dict, interval: int = 30):
    """Background task that expires stale questions and sends timeout notifications."""
    timeout_action = config.get("defaults", {}).get("timeout_action", "deny")
    from .formatter import format_timeout

    while True:
        try:
            expired = await queue.expire_stale()
            for q in expired:
                msg = format_timeout(q, timeout_action)
                try:
                    await telegram_sender.send(msg)
                except Exception:
                    logger.exception("Failed to send timeout notification for %s", q.short_id)
        except Exception:
            logger.exception("Error in expiry loop")
        await asyncio.sleep(interval)
