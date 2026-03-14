"""Claude Code Relay — FastAPI service that bridges Claude Code hooks to Telegram via OpenClaw."""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import time
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .formatter import format_approval, format_denial, format_question, format_relay_started
from .hook_parser import parse_hook
from .models import HookResponse, ReplyPayload
from .queue_manager import QueueManager, run_expiry_loop
from .telegram_sender import TelegramSender

# ── Configuration ───────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent.parent
CONFIG_PATH = SKILL_DIR / "config.yaml"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {
        "server": {"host": "127.0.0.1", "port": 8400},
        "telegram": {"bot_token": "", "chat_id": ""},
        "timeouts": {"default_seconds": 1800, "expiry_check_seconds": 30},
        "defaults": {"timeout_action": "deny"},
        "logging": {"level": "INFO"},
    }


config = load_config()

# ── Logging ─────────────────────────────────────────────────────────────────


def setup_logging():
    log_cfg = config.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)

    fmt = logging.Formatter("%(asctime)s  %(name)-28s  %(levelname)-5s  %(message)s")
    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    log_file = log_cfg.get("file")
    if log_file:
        p = Path(log_file)
        if not p.is_absolute():
            p = SKILL_DIR / p
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            p, maxBytes=50 * 1024 * 1024, backupCount=3,
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)


setup_logging()
logger = logging.getLogger("claudecoderelay.relay")

# ── Globals ─────────────────────────────────────────────────────────────────

db_path = SKILL_DIR / "data" / "queue.db"
queue = QueueManager(db_path)

tg_cfg = config.get("telegram", {})
telegram = TelegramSender(tg_cfg.get("bot_token", ""), tg_cfg.get("chat_id", ""))

_start_time = time.time()

# Reply event system: question_id -> asyncio.Event
_reply_events: dict[str, asyncio.Event] = {}

# ── App lifecycle ───────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    await queue.init()
    await telegram.init()

    expiry_interval = config.get("timeouts", {}).get("expiry_check_seconds", 30)
    expiry_task = asyncio.create_task(
        run_expiry_loop(queue, telegram, config, expiry_interval)
    )

    port = config.get("server", {}).get("port", 8400)
    logger.info("Claude Code Relay started on port %s", port)

    # Send startup notification to Telegram
    try:
        await telegram.send(format_relay_started(port))
    except Exception:
        logger.warning("Could not send startup notification to Telegram")

    yield

    expiry_task.cancel()
    await telegram.close()
    await queue.close()
    logger.info("Claude Code Relay stopped")


app = FastAPI(title="Claude Code Relay", version="1.0.0", lifespan=lifespan)

# ── Endpoints ───────────────────────────────────────────────────────────────


@app.post("/api/question")
async def receive_question(request: Request):
    """Receive a question from Claude Code hook. Send Telegram notification. Long-poll for reply."""
    body = await request.json()

    # Log raw payload for debugging hook format
    logger.debug("Raw hook payload: %s", body)

    # Parse hook payload into a Question
    question = parse_hook(body)

    timeout_cfg = config.get("timeouts", {})
    question.timeout_seconds = timeout_cfg.get("default_seconds", 1800)

    # If it's a Stop notification, just notify and return immediately
    if question.hook_type == "Stop":
        await queue.add_question(question)
        msg = format_question(question)
        await telegram.send(msg)
        return JSONResponse({"decision": "approve", "reason": "notification acknowledged"})

    # Store question
    await queue.add_question(question)

    # Send Telegram notification
    msg = format_question(question)
    msg_id = await telegram.send(msg)
    if msg_id:
        await queue.set_telegram_message_id(question.id, msg_id)
    else:
        logger.warning("Could not send Telegram notification for %s", question.short_id)

    # Create reply event
    event = asyncio.Event()
    _reply_events[question.id] = event

    # Long-poll: wait for reply
    poll_interval = timeout_cfg.get("poll_interval_seconds", 2)
    deadline = time.time() + question.timeout_seconds

    try:
        while time.time() < deadline:
            remaining = deadline - time.time()
            wait_time = min(poll_interval, remaining)
            if wait_time <= 0:
                break
            try:
                await asyncio.wait_for(event.wait(), timeout=wait_time)
            except asyncio.TimeoutError:
                pass

            q = await queue.get_question(question.id)
            if q and q.status == "answered":
                return JSONResponse(
                    HookResponse(
                        decision=q.decision or "approve",
                        reason="User approved via OpenClaw" if q.decision == "approve"
                        else "User denied via OpenClaw",
                    ).model_dump()
                )
            if q and q.status in ("expired", "cancelled"):
                break
    finally:
        _reply_events.pop(question.id, None)

    # Timeout / expired / cancelled
    default_action = config.get("defaults", {}).get("timeout_action", "deny")
    return JSONResponse(
        HookResponse(
            decision=default_action,
            reason=f"No reply within {question.timeout_seconds // 60} minutes",
        ).model_dump()
    )


@app.post("/api/reply/{question_id}")
async def receive_reply(question_id: str, payload: ReplyPayload):
    """Receive a reply from the OpenClaw agent (via relay_reply.sh)."""
    # Normalise decision
    decision = _normalise_decision(payload.reply)

    # Look up question (supports both full ID and short_id)
    q = await queue.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="No pending question with that ID")

    stored = await queue.store_reply(q.id, payload.reply, decision, payload.replied_at)
    if not stored:
        raise HTTPException(status_code=409, detail="Question already answered or expired")

    # Send confirmation to Telegram
    q_updated = await queue.get_question(q.id)
    if q_updated:
        if decision == "approve":
            await telegram.send(format_approval(q_updated))
        else:
            await telegram.send(format_denial(q_updated))

    # Wake the long-poll
    event = _reply_events.get(q.id)
    if event:
        event.set()

    return {"status": "ok", "question_id": q.id, "decision": decision}


@app.get("/api/pending")
async def get_pending():
    """Return all unanswered questions."""
    questions = await queue.get_pending()
    return {"pending": [q.model_dump() for q in questions]}


@app.get("/api/status")
async def get_status():
    """Health check — uptime, pending count, last activity."""
    stats = await queue.stats()
    return {
        "status": "running",
        "uptime_seconds": int(time.time() - _start_time),
        "queue": stats,
        "port": config.get("server", {}).get("port", 8400),
    }


@app.get("/api/history")
async def get_history(count: int = Query(default=10, ge=1, le=100)):
    """Recent questions with outcomes."""
    questions = await queue.get_history(count)
    return {"history": [q.model_dump() for q in questions]}


@app.delete("/api/question/{question_id}")
async def cancel_question(question_id: str):
    """Cancel a pending question, or cancel all with id='all'."""
    if question_id == "all":
        count = await queue.cancel_all()
        # Wake all long-polls
        for event in _reply_events.values():
            event.set()
        _reply_events.clear()
        return {"status": "cancelled", "count": count}

    q = await queue.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="No pending question with that ID")

    cancelled = await queue.cancel_question(q.id)
    if not cancelled:
        raise HTTPException(status_code=409, detail="Question already answered or expired")

    event = _reply_events.get(q.id)
    if event:
        event.set()

    return {"status": "cancelled", "question_id": q.id}


@app.post("/api/test")
async def create_test_question():
    """Create a test pending question for verifying the reply flow."""
    from .models import Question

    q = Question(
        hook_type="PreToolUse",
        tool_name="Bash",
        tool_input='{"command": "echo \'Hello from Claude Code Relay test!\'"}',
        formatted_question="echo 'Hello from Claude Code Relay test!'",
    )
    q.timeout_seconds = config.get("timeouts", {}).get("default_seconds", 1800)
    await queue.add_question(q)

    msg = format_question(q)
    msg_id = await telegram.send(msg)
    if msg_id:
        await queue.set_telegram_message_id(q.id, msg_id)

    return {
        "status": "created",
        "question_id": q.id,
        "short_id": q.short_id,
        "message": "Test question created. Reply via OpenClaw to test the flow.",
    }


# ── Helpers ─────────────────────────────────────────────────────────────────

_APPROVE_WORDS = {"yes", "y", "approve", "allow", "ok", "sure", "go", "do it", "go ahead"}
_DENY_WORDS = {"no", "n", "deny", "reject", "block", "stop", "don't", "dont"}


def _normalise_decision(reply: str) -> str:
    lower = reply.strip().lower()
    if lower in _APPROVE_WORDS:
        return "approve"
    if lower in _DENY_WORDS:
        return "deny"
    return reply.strip()


# ── Run directly ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "relay.main:app",
        host=config["server"]["host"],
        port=config["server"]["port"],
        reload=False,
    )
