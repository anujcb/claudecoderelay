"""Pydantic request/response models for Claude Code Relay."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _short_id() -> str:
    return uuid.uuid4().hex[:6]


# ── Incoming from Claude Code hook ──────────────────────────────────────────

class HookPayload(BaseModel):
    """Raw payload POSTed by a Claude Code HTTP hook."""
    hook_type: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    session_id: Optional[str] = None
    model_config = {"extra": "allow"}


# ── Internal question record ────────────────────────────────────────────────

class Question(BaseModel):
    id: str = Field(default_factory=_new_id)
    short_id: str = Field(default_factory=_short_id)
    created_at: str = Field(default_factory=_utcnow)
    hook_type: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[str] = None       # JSON-stringified
    formatted_question: Optional[str] = None
    telegram_message_id: Optional[int] = None
    timeout_seconds: int = 1800
    status: str = "pending"
    reply: Optional[str] = None
    decision: Optional[str] = None
    replied_at: Optional[str] = None


# ── Reply from agent (via relay_reply.sh) ───────────────────────────────────

class ReplyPayload(BaseModel):
    reply: str
    replied_at: str = Field(default_factory=_utcnow)


# ── Response back to Claude Code hook ───────────────────────────────────────

class HookResponse(BaseModel):
    """Returned to the waiting Claude Code HTTP hook."""
    decision: str          # "approve" | "deny" | "skip"
    reason: str = ""
