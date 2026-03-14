# Claude Code Relay

OpenClaw skill that bridges Claude Code (VS Code on desktop) to Telegram.

## Architecture

- **relay/** — Python FastAPI service (port 8400, localhost only, via SSH tunnel)
- **scripts/** — Shell scripts called by the OpenClaw agent
- **SKILL.md** — Teaches the OpenClaw agent when/how to use this skill

## How it works

1. Claude Code HTTP hook POSTs to `localhost:8400/api/question` (SSH tunnel to server)
2. Relay stores question in SQLite, sends Telegram notification via OpenClaw's bot
3. Relay long-polls (holds HTTP connection open) waiting for reply
4. User replies in OpenClaw chat → agent runs `relay_reply.sh` → POSTs to `/api/reply/{id}`
5. Relay returns reply on the original HTTP connection → Claude Code continues

No separate Telegram bot. Relay only sends; OpenClaw agent handles incoming replies.

## Key files

- `relay/main.py` — FastAPI app (question, reply, pending, status, history, test endpoints)
- `relay/telegram_sender.py` — Send-only Telegram client using OpenClaw's bot token
- `relay/queue_manager.py` — SQLite queue with expiry
- `relay/hook_parser.py` — Parses Claude Code hook payloads
- `relay/formatter.py` — Telegram message formatting
- `relay/dangerous_commands.py` — Regex patterns for risky commands

## Development

Relay uses relative imports (`from .models import ...`) — run as a module:
```bash
python -m uvicorn relay.main:app --host 127.0.0.1 --port 8400 --app-dir .
```

## Deploy

```bash
# Copy to server, then:
bash scripts/setup.sh
bash scripts/relay_start.sh
```
