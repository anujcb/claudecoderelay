# Claude Code Relay

**Remote control for Claude Code through Telegram.**

Claude Code Relay is an [OpenClaw](https://openclaw.ai) skill that bridges your Claude Code sessions (running in VS Code on your desktop) to your Telegram. When Claude Code needs permission to run a command, edit a file, or make a decision — the question arrives in your Telegram chat. Reply naturally, and Claude Code continues working.

No extra bots. No exposed ports. Just your existing OpenClaw setup + an SSH tunnel.

---

## How It Works

```
  Your Desktop                              Your Server (EC2/VPS)
┌──────────────────┐               ┌──────────────────────────────┐
│ Claude Code      │   SSH Tunnel  │  Claude Code Relay           │
│ (VS Code)        │   port 8400   │  (FastAPI on localhost)      │
│      │           │               │       │                      │
│  HTTP Hook       │               │  Sends notification via      │
│      │           │               │  OpenClaw's Telegram bot     │
│ localhost:8400 ──┼── tunnel ────>│       │                      │
│                  │               │  User replies in Telegram    │
│ (reply returns)  │<── tunnel ────┤  OpenClaw agent runs         │
│      │           │               │  relay_reply.sh              │
│ Claude Code      │               │       │                      │
│ (continues)      │               │  Reply sent back to relay    │
└──────────────────┘               └──────────────────────────────┘
                                            │
                                   ┌────────▼────────┐
                                   │    Telegram      │
                                   │   (Your Phone)   │
                                   └────────┬────────┘
                                            │
                                       You reply
```

### The Flow

1. Claude Code wants to run `npm test` → HTTP hook fires
2. Request tunnels to your server via SSH
3. Relay stores the question and sends a Telegram notification
4. You see it on your phone: *"🤖 Claude Code wants to run: npm test. Approve?"*
5. You reply "yes" to the OpenClaw agent
6. Agent sends your reply back to the relay
7. Relay returns the answer to the waiting Claude Code hook
8. Claude Code continues working

### Graceful Degradation

If the tunnel is down, the relay is stopped, or anything else fails — Claude Code works exactly as it does today, with on-screen prompts in VS Code. Claude Code Relay is purely additive.

---

## Quick Start

### Prerequisites

- [OpenClaw](https://openclaw.ai) running on a server with Telegram connected
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed on your desktop
- SSH access to your server (you already have this if you run OpenClaw)

### Install

```bash
clawhub install claudecoderelay
```

Or manually:

```bash
# On your server
mkdir -p ~/.openclaw/skills/claudecoderelay
git clone https://github.com/anthropics/claudecoderelay.git
cp -r claudecoderelay/* ~/.openclaw/skills/claudecoderelay/
```

### Setup

Tell your OpenClaw agent:

```
Set up claude code relay
```

Or run manually on your server:

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/setup.sh
```

The setup script will:
- Install Python dependencies
- Auto-detect your bot token and chat ID from OpenClaw's config
- Create the relay configuration
- Print instructions for your desktop

### Desktop Configuration

**1. SSH Tunnel** — Add port 8400 to your existing SSH tunnel:

```bash
ssh -i /path/to/key.pem -N \
    -L 8400:127.0.0.1:8400 \
    user@your-server
```

**2. Claude Code Hook** — Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "type": "http",
        "url": "http://localhost:8400/api/question"
      }
    ]
  }
}
```

### Start

Tell your OpenClaw agent:

```
Start claude code relay
```

Or run manually:

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_start.sh
```

---

## Usage

### Through OpenClaw (Natural Language)

Just talk to your OpenClaw agent in Telegram:

| You say | What happens |
|---------|-------------|
| "Start claude code relay" | Starts the relay service |
| "Stop claude code relay" | Stops the relay service |
| "Claude code status" | Shows relay health and queue stats |
| "What's claude code doing?" | Shows pending questions and last activity |
| "yes" / "approve" | Approves the most recent pending question |
| "no" / "deny" | Denies the most recent pending question |
| "Claude code history" | Shows recent questions and outcomes |

### Permission Notifications

When Claude Code needs permission, you'll see messages like:

**Normal request:**
```
🤖 Claude Code [abc123]
━━━━━━━━━━━━━━━━━━━━
🔧 Run: npm test

Reply in OpenClaw: approve or deny
⏱️ 30 min timeout
```

**Dangerous command (auto-flagged):**
```
🔴 Claude Code [def456]
━━━━━━━━━━━━━━━━━━━━
🔧 Run: git push --force origin main

⚠️ FORCE PUSH — review carefully!
Reply in OpenClaw: approve or deny
⏱️ 30 min timeout
```

**File edit:**
```
🤖 Claude Code [ghi789]
━━━━━━━━━━━━━━━━━━━━
📝 Edit: src/routes/orders.js

Reply in OpenClaw: approve or deny
⏱️ 30 min timeout
```

### Dangerous Command Detection

The relay automatically flags risky commands with a 🔴 warning:

- `rm -rf`, `rm -r` — recursive deletion
- `git push --force` — force push
- `git reset --hard` — hard reset
- `DROP TABLE`, `DELETE FROM` — database destructive
- `sudo` — elevated privileges
- `chmod 777` — insecure permissions
- `curl | sh` — remote code execution
- `.env`, `password`, `secret`, `token` — sensitive file access

---

## Architecture

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Relay Service** | Server (Python/FastAPI) | Receives hooks, stores questions, sends Telegram notifications, long-polls for replies |
| **Shell Scripts** | Server | Called by OpenClaw agent to interact with the relay |
| **SKILL.md** | Server | Teaches the OpenClaw agent when and how to use this skill |
| **SSH Tunnel** | Desktop | Securely connects Claude Code to the relay |
| **HTTP Hook** | Desktop | Sends Claude Code events to the relay |

### How Replies Work (No Separate Bot)

Claude Code Relay uses OpenClaw's **existing** Telegram bot. No second bot, no polling conflicts.

- **Sending:** The relay calls the Telegram Bot API directly to send notifications
- **Receiving:** The OpenClaw agent handles incoming messages. When you say "yes" or "approve," the agent recognizes it as a Claude Code Relay action and runs `relay_reply.sh`

### Security

- Relay binds to `127.0.0.1` only — not accessible from the internet
- SSH tunnel provides encryption and authentication — no new ports exposed
- Uses OpenClaw's existing bot token — no extra credentials
- No Claude Code credentials transit the relay — only question text
- Config file is gitignored — secrets never committed

---

## API Reference

The relay exposes these endpoints on `localhost:8400`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/question` | Receive question from Claude Code hook (long-polls for reply) |
| `POST` | `/api/reply/{id}` | Submit a reply to a pending question |
| `GET` | `/api/pending` | List all pending questions |
| `GET` | `/api/status` | Relay health, uptime, queue stats |
| `GET` | `/api/history?count=N` | Recent questions with outcomes |
| `DELETE` | `/api/question/{id}` | Cancel a specific question |
| `DELETE` | `/api/question/all` | Cancel all pending questions |
| `POST` | `/api/test` | Create a test question for verification |

---

## Scripts Reference

All scripts are in `scripts/` and output JSON.

| Script | Purpose |
|--------|---------|
| `setup.sh` | First-time setup — installs deps, creates config |
| `relay_start.sh` | Start the relay as a background process |
| `relay_stop.sh` | Stop the relay |
| `relay_status.sh` | Check relay health and queue stats |
| `relay_pending.sh` | List pending questions |
| `relay_reply.sh <id> <decision>` | Reply to a question (approve/deny/text) |
| `relay_history.sh [count]` | Show recent questions (default: 10) |
| `relay_cancel.sh <id\|all>` | Cancel questions |
| `relay_config.sh [key] [value]` | View or update configuration |
| `relay_notify.sh <message>` | Send a Telegram message directly |
| `relay_test.sh` | End-to-end test |

---

## Configuration

Configuration lives in `config.yaml` (auto-created by setup):

```yaml
server:
  host: "127.0.0.1"
  port: 8400

telegram:
  bot_token: "your-bot-token"
  chat_id: "your-chat-id"

timeouts:
  default_seconds: 1800      # 30 min default
  max_seconds: 7200           # 2 hour max
  expiry_check_seconds: 30    # Check for expired questions

defaults:
  timeout_action: "deny"      # What to return on timeout: deny | skip

logging:
  level: "INFO"
  file: "logs/relay.log"
```

Update config via the agent ("configure code relay") or directly:

```bash
bash scripts/relay_config.sh timeout 3600        # 1 hour timeout
bash scripts/relay_config.sh timeout_action skip  # Skip on timeout instead of deny
bash scripts/relay_config.sh chat_id 123456789    # Change chat ID
```

Restart the relay after config changes.

---

## Troubleshooting

### Relay won't start

```bash
# Check logs
cat ~/.openclaw/skills/claudecoderelay/logs/relay.log

# Check if port is in use
lsof -i :8400

# Re-run setup
bash scripts/setup.sh
```

### No Telegram notifications

```bash
# Verify config
bash scripts/relay_config.sh

# Test notification directly
bash scripts/relay_notify.sh "test"
```

### Tunnel issues

```bash
# From desktop — should return JSON
curl.exe http://localhost:8400/api/status

# If connection refused: tunnel is down, restart it
```

### Questions timing out

Default timeout is 30 minutes. Increase it:

```bash
bash scripts/relay_config.sh timeout 3600
```

See [troubleshooting guide](references/troubleshooting.md) for more.

---

## Roadmap

| Phase | Feature |
|-------|---------|
| **1 (current)** | Permission requests via hooks |
| 2 | Auto-pilot rules (auto-approve `npm test`, auto-deny `rm -rf`) |
| 3 | Inline question capture (conversational questions from Claude Code) |
| 4 | Systemd service for auto-start on reboot |
| 5 | Multi-desktop support |
| 6 | Statistics dashboard |

---

## Requirements

### Server

- Python 3.10+
- OpenClaw with Telegram connected
- Packages: `fastapi`, `uvicorn`, `httpx`, `aiosqlite`, `pyyaml`

### Desktop

- Claude Code CLI
- SSH access to server
- Any OS (Windows, macOS, Linux)

---

## License

MIT

---

## Author

Built by [Anil](https://github.com/anil) for the OpenClaw community.
