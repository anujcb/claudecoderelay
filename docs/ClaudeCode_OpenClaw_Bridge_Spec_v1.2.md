# ClaudeBridge: Claude Code ↔ OpenClaw Telegram Bridge

## Project Specification v1.2

**Author:** Anil  
**Date:** March 14, 2026  
**Status:** Draft  
**Change from v1.1:** Replaced WebSocket architecture with SSH tunnel. Eliminated desktop client component entirely. Much simpler — only one service to build and deploy (on EC2).

---

## 1. Executive Summary

ClaudeBridge is a single service running on EC2 alongside OpenClaw that bridges Claude Code (running in VS Code on a Windows desktop) to your existing OpenClaw Telegram channel. An SSH tunnel (the same mechanism you already use for the OpenClaw control panel) makes the EC2 service appear as localhost on your desktop, so Claude Code hooks POST directly to it.

### The Problem

Claude Code frequently needs human input during long-running tasks — permission approvals, design decisions, clarifications. If you're away from your desktop, the session stalls.

### The Solution

An SSH tunnel exposes the ClaudeBridge relay on EC2 as localhost:8400 on your desktop. Claude Code hooks POST questions there. The relay forwards them through OpenClaw to your Telegram. You reply. The relay returns your answer to the waiting hook. Claude Code continues.

---

## 2. Architecture

### High-Level Flow

```
  DESKTOP (Windows)                           AWS EC2 (3.101.144.251)
┌──────────────────────┐               ┌──────────────────────────┐
│                      │               │                          │
│  Claude Code         │   SSH Tunnel  │   ClaudeBridge Relay     │
│  (VS Code)           │   port 8400   │   (FastAPI :8400)        │
│       │              │               │       │                  │
│   HTTP Hook          │               │       ▼                  │
│       │              │               │   OpenClaw Custom Skill  │
│       ▼              │               │   (localhost webhook)    │
│  localhost:8400 ─────┼── tunnel ────>│       │                  │
│                      │               │       ▼                  │
│  (reply returns on   │               │   Telegram Bot API       │
│   same HTTP request) │<── tunnel ────┤   (existing channel)     │
│       │              │               │                          │
│       ▼              │               └──────────────────────────┘
│  Claude Code                                  │
│  (continues work)                             ▼
│                      │               ┌──────────────┐
└──────────────────────┘               │   Telegram    │
                                       │  (Your Phone) │
                                       └──────┬───────┘
                                              │
                                         You reply
```

### Why SSH Tunnel?

You already use this for the OpenClaw control panel:
```
ssh -i F:\work\OpenClaw\Bot1\clawed1.pem -N -L 18789:127.0.0.1:18789 ubuntu@3.101.144.251
```

Just add another port forwarding flag. No new infrastructure, no SSL certs, no security group changes, no auth tokens. The tunnel handles encryption and access control.

### Components (only 2 to build)

| Component | Location | Role | Tech |
|-----------|----------|------|------|
| **ClaudeBridge Relay** | EC2 | Receives questions, notifies OpenClaw skill, long-polls for reply, returns it | Python FastAPI |
| **OpenClaw Custom Skill** | EC2 | Formats questions for Telegram, captures replies, sends to relay | OpenClaw Skill (JS) |

Everything else is existing infrastructure:

| Existing | Role |
|----------|------|
| Claude Code HTTP hooks | Sends questions to localhost:8400 |
| SSH tunnel | Connects localhost:8400 to EC2:8400 |
| OpenClaw on EC2 | Telegram messaging agent |
| Telegram | User-facing interface |

---

## 3. SSH Tunnel Setup

### Combined Tunnel Command

Add port 8400 to your existing SSH command:

```powershell
ssh -i F:\work\OpenClaw\Bot1\clawed1.pem -N -L 18789:127.0.0.1:18789 -L 8400:127.0.0.1:8400 ubuntu@3.101.144.251
```

This forwards both:
- `localhost:18789` → EC2:18789 (OpenClaw control panel — existing)
- `localhost:8400` → EC2:8400 (ClaudeBridge relay — new)

### Convenience Script

`G:\work\ClaudeBridge\scripts\tunnel.ps1`:

```powershell
# Start SSH tunnel for OpenClaw control panel + ClaudeBridge
# Run this before starting any Claude Code session

$keyPath = "F:\work\OpenClaw\Bot1\clawed1.pem"
$ec2Host = "ubuntu@3.101.144.251"

Write-Host "Starting SSH tunnel to EC2..." -ForegroundColor Cyan
Write-Host "  Port 18789 -> OpenClaw control panel" -ForegroundColor Gray
Write-Host "  Port 8400  -> ClaudeBridge relay" -ForegroundColor Gray
Write-Host ""
Write-Host "Keep this window open. Press Ctrl+C to disconnect." -ForegroundColor Yellow

ssh -i $keyPath -N `
    -L 18789:127.0.0.1:18789 `
    -L 8400:127.0.0.1:8400 `
    -o ServerAliveInterval=60 `
    -o ServerAliveCountMax=3 `
    $ec2Host
```

The `-o ServerAliveInterval=60` keeps the tunnel alive and detects drops within 3 minutes.

### Auto-Reconnect Script (Optional)

`G:\work\ClaudeBridge\scripts\tunnel-persistent.ps1`:

```powershell
# Auto-reconnecting SSH tunnel
$keyPath = "F:\work\OpenClaw\Bot1\clawed1.pem"
$ec2Host = "ubuntu@3.101.144.251"

while ($true) {
    Write-Host "[$(Get-Date)] Connecting SSH tunnel..." -ForegroundColor Cyan
    
    ssh -i $keyPath -N `
        -L 18789:127.0.0.1:18789 `
        -L 8400:127.0.0.1:8400 `
        -o ServerAliveInterval=60 `
        -o ServerAliveCountMax=3 `
        -o ExitOnForwardFailure=yes `
        $ec2Host

    Write-Host "[$(Get-Date)] Tunnel disconnected. Reconnecting in 5 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
```

---

## 4. Component Specifications

### 4.1 ClaudeBridge Relay (EC2)

**Location:** `/home/ubuntu/claudebridge/relay/`

**Purpose:** Receives questions from Claude Code (via SSH tunnel), stores them, notifies OpenClaw skill, long-polls until reply arrives from Telegram, returns reply.

#### How Long-Polling Works

1. Claude Code hook POSTs question to `localhost:8400/api/question` (tunneled to EC2)
2. Relay stores question in SQLite with status `pending`
3. Relay POSTs notification to OpenClaw skill webhook (`localhost:3000/...`)
4. Relay **holds the HTTP connection open** — async wait loop checking for reply every 2 seconds
5. User replies on Telegram → OpenClaw skill POSTs reply to relay at `/api/reply/{id}`
6. Relay finds the matching pending question, stores the reply
7. The waiting async loop picks up the reply and returns it as the HTTP response
8. Claude Code hook receives the reply and passes it to Claude Code

The key insight: the single HTTP request from Claude Code stays open until you reply. The SSH tunnel keeps the TCP connection alive. No polling from the desktop side needed.

#### Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/question` | Receives question from Claude Code hook. Long-polls until reply or timeout. |
| POST | `/api/reply/{question_id}` | Receives reply from OpenClaw skill. Unblocks the waiting `/api/question`. |
| GET | `/api/pending` | Returns unanswered questions (backup for OpenClaw skill). |
| GET | `/api/status` | Health check — queue depth, uptime, connection info. |
| DELETE | `/api/question/{question_id}` | Cancel/dismiss a pending question. |

#### Question Payload (from Claude Code Hook)

The exact payload depends on what Claude Code's HTTP hooks send. The relay should accept the hook's native format and extract:

```json
{
  "question_id": "auto-generated-uuid",
  "timestamp": "2026-03-14T10:30:00Z",
  "hook_type": "PreToolUse",
  "tool_name": "bash",
  "tool_input": "npm test",
  "project": "RivvexProject",
  "session_id": "claude-session-id"
}
```

The relay wraps this into a richer notification for OpenClaw:

```json
{
  "question_id": "uuid",
  "type": "permission",
  "question": "Claude wants to run: npm test",
  "options": ["approve", "deny"],
  "context": {
    "project": "RivvexProject",
    "tool": "bash",
    "command": "npm test"
  },
  "timeout_seconds": 1800
}
```

#### Reply Payload (from OpenClaw Skill)

```json
{
  "question_id": "uuid",
  "reply": "approve",
  "replied_at": "2026-03-14T10:32:15Z"
}
```

#### Hook Response (back to Claude Code)

The relay returns a response that Claude Code's hook system can interpret:

```json
{
  "decision": "approve",
  "reason": "User approved via Telegram"
}
```

Or on timeout:

```json
{
  "decision": "deny",
  "reason": "No reply received within 30 minutes"
}
```

**Important:** The exact response format needs to match what Claude Code HTTP hooks expect. This should be verified against Claude Code's hook documentation during implementation.

#### Data Store

SQLite at `relay/data/queue.db`:

```sql
CREATE TABLE questions (
  id TEXT PRIMARY KEY,
  timestamp TEXT NOT NULL,
  hook_type TEXT,
  tool_name TEXT,
  tool_input TEXT,
  project TEXT,
  session_id TEXT,
  formatted_question TEXT,
  options TEXT,                -- JSON array or null
  timeout_seconds INTEGER DEFAULT 1800,
  status TEXT DEFAULT 'pending',  -- pending | answered | expired | cancelled
  reply TEXT,
  replied_at TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### Auto-Expiry

A background task runs every 30 seconds, checks for questions where `created_at + timeout_seconds < now`, marks them as `expired`. This ensures the long-polling loop terminates and returns a timeout response.

#### Configuration

`relay/config.yaml`:

```yaml
server:
  host: "127.0.0.1"    # Bind to localhost only — SSH tunnel handles access
  port: 8400

openclaw:
  skill_webhook_url: "http://localhost:3000/api/skills/claudebridge/notify"
  # Adjust port/path to match your OpenClaw instance

timeouts:
  default_seconds: 1800       # 30 min wait for reply
  max_seconds: 7200            # 2 hour absolute max
  poll_interval_seconds: 2     # Check for reply every 2s
  expiry_check_seconds: 30     # Check for expired questions every 30s

notifications:
  reminder_after_seconds: 300  # Telegram reminder after 5 min
  max_reminders: 3

defaults:
  timeout_action: "deny"       # What to return when timeout: deny | skip | ask_again

logging:
  level: "INFO"
  file: "/home/ubuntu/claudebridge/relay/logs/relay.log"
  max_size_mb: 50
  backup_count: 3
```

---

### 4.2 Claude Code HTTP Hooks (Desktop)

**Location:** `~/.claude/settings.json` (global)

**Purpose:** Intercept Claude Code events and forward to localhost:8400 (tunneled to EC2).

#### Hook Configuration

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "type": "http",
        "url": "http://localhost:8400/api/question",
        "description": "Forward permission requests to Telegram via ClaudeBridge"
      }
    ],
    "Stop": [
      {
        "type": "http",
        "url": "http://localhost:8400/api/question",
        "description": "Notify Telegram when Claude Code session ends"
      }
    ]
  }
}
```

#### Hook Behavior

- Hook POSTs to `localhost:8400` → SSH tunnel → EC2 relay
- The hook **blocks** waiting for the HTTP response (long-poll)
- If tunnel is down: connection refused → hook fails silently → Claude Code proceeds normally
- If relay returns timeout: hook returns default deny/skip → Claude Code continues

#### Graceful Degradation

If the tunnel isn't running, Claude Code works exactly as it does today — hooks fail silently and Claude Code proceeds with its normal interactive prompts on screen. ClaudeBridge is purely additive.

#### Important Limitation

Claude Code hooks fire on lifecycle events (PreToolUse, PostToolUse, Stop, etc.). Free-form conversational questions ("Should I use approach A or B?") appear inline and don't trigger hooks. Phase 1 focuses on permission requests. See Section 8 for capturing inline questions.

---

### 4.3 OpenClaw Custom Skill (EC2)

**Location:** OpenClaw skills directory on EC2 (e.g. `~/.openclaw/skills/claudebridge/`)

**Purpose:** Receives notifications from relay (same machine, localhost), formats for Telegram, captures replies, sends back to relay.

#### Skill Manifest

`skill.json`:

```json
{
  "name": "claudebridge",
  "displayName": "Claude Code Bridge",
  "description": "Forwards Claude Code questions to Telegram and sends replies back",
  "version": "1.0.0",
  "author": "Anil",
  "permissions": ["http", "messaging"],
  "triggers": [
    {
      "type": "webhook",
      "endpoint": "/api/skills/claudebridge/notify",
      "method": "POST"
    },
    {
      "type": "message",
      "pattern": "^/claude\\s+.*",
      "description": "Manual commands"
    },
    {
      "type": "message",
      "pattern": "^(yes|no|approve|deny|allow|reject|skip|[1-9])$",
      "description": "Quick reply to most recent pending question",
      "condition": "hasPendingQuestion"
    }
  ]
}
```

#### Skill Logic

```
INCOMING WEBHOOK (from relay, localhost):

  1. Receive question payload
  2. Format as readable Telegram message
  3. If options exist, add inline keyboard buttons
  4. Send to Telegram via OpenClaw messaging API
  5. Store question_id as active pending question (in-memory or skill state)

INCOMING TELEGRAM REPLY (from user):

  1. Check if there's a pending question
  2. If user typed a number and options exist, map to option text
  3. POST reply to relay: http://localhost:8400/api/reply/{question_id}
  4. Send confirmation reaction/message in Telegram
  5. Clear pending question state

ERROR HANDLING:

  - If relay is unreachable: tell user "⚠️ Bridge relay is down"
  - If no pending question: tell user "No pending questions from Claude Code"
  - If reply POST fails: retry once, then tell user to try again
```

#### Telegram Message Formats

**Permission request:**
```
🤖 Claude Code
━━━━━━━━━━━━━━━━━━━━━━━━
📁 RivvexProject
🔧 Running: npm test

Allow? Reply Yes or No
━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ 30 min timeout
```

**Dangerous command (flagged with urgency):**
```
🔴 Claude Code — REVIEW CAREFULLY
━━━━━━━━━━━━━━━━━━━━━━━━
📁 RivvexProject
🔧 Running: git push origin staging --force

⚠️ This is a force push!
Allow? Reply Yes or No
━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ 30 min timeout
```

**File edit permission:**
```
🤖 Claude Code
━━━━━━━━━━━━━━━━━━━━━━━━
📁 RivvexProject
📝 Edit: rivvex-api/src/routes/orders.js

Allow? Reply Yes or No
━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ 30 min timeout
```

**Task complete (notification, no reply needed):**
```
✅ Claude Code — Done
━━━━━━━━━━━━━━━━━━━━━━━━
📁 RivvexProject
🔧 Refactoring order cancellation logic

12 min · 4 files · 28/28 tests pass
```

**Timeout notification:**
```
⏱️ Claude Code — Timed Out
━━━━━━━━━━━━━━━━━━━━━━━━
No reply for: npm test
Default action: denied
```

#### Telegram Commands

| Command | Action |
|---------|--------|
| `/claude status` | Pending questions, relay health |
| `/claude reply <id> <text>` | Reply to specific question |
| `/claude approve` | Approve most recent |
| `/claude deny` | Deny most recent |
| `/claude history` | Last 10 questions |
| `/claude auto npm test approve` | Add auto-rule (Phase 2) |

**Quick replies:** If one pending question exists, plain text (yes/no/number) routes to it automatically.

---

## 5. Directory Structure

### Desktop (Windows) — minimal

```
G:\work\ClaudeBridge\
├── README.md
├── CLAUDE.md                        # For Claude Code to understand this project
├── scripts/
│   ├── tunnel.ps1                   # SSH tunnel with both ports
│   ├── tunnel-persistent.ps1        # Auto-reconnecting tunnel
│   └── test_flow.py                 # Simulate a question to test round-trip
└── docs/
    ├── setup-guide.md
    └── troubleshooting.md
```

### EC2 (Linux) — the actual project

```
/home/ubuntu/claudebridge/
├── relay/
│   ├── main.py                      # FastAPI app entry point
│   ├── config.yaml                  # Configuration
│   ├── config.yaml.example          # Template (committed to git)
│   ├── requirements.txt             # Python dependencies
│   ├── models.py                    # Pydantic request/response models
│   ├── queue_manager.py             # SQLite operations
│   ├── openclaw_notifier.py         # POST to OpenClaw skill webhook
│   ├── hook_parser.py               # Parse Claude Code hook payloads
│   ├── data/
│   │   └── queue.db                 # SQLite (auto-created, gitignored)
│   └── logs/
│       └── relay.log                # Logs (gitignored)
│
├── openclaw-skill/
│   ├── skill.json                   # Skill manifest
│   ├── index.js                     # Main skill logic
│   ├── formatter.js                 # Telegram message formatting
│   ├── reply_handler.js             # Reply matching and forwarding
│   ├── dangerous_commands.js        # List of commands flagged as high-urgency
│   └── package.json
│
├── scripts/
│   ├── setup.sh                     # One-time EC2 setup
│   ├── deploy-skill.sh              # Copy skill to OpenClaw directory + restart
│   └── test_relay.sh                # Test relay endpoints directly on EC2
│
├── claudebridge.service             # systemd unit file
├── .gitignore
└── README.md
```

---

## 6. Setup and Installation

### Prerequisites

- Existing SSH access to EC2 (you already have this)
- OpenClaw running on EC2 with Telegram connected (you already have this)
- Claude Code CLI installed on desktop (done)
- Python 3.10+ on EC2

### Step 1: Deploy Relay to EC2

```bash
# SSH into your EC2
ssh -i F:\work\OpenClaw\Bot1\clawed1.pem ubuntu@3.101.144.251

# Clone or copy the project
cd /home/ubuntu
mkdir -p claudebridge/relay
cd claudebridge/relay

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn aiohttp aiosqlite pyyaml

# Configure
cp config.yaml.example config.yaml
nano config.yaml
# Set openclaw.skill_webhook_url to match your OpenClaw setup
```

### Step 2: Install OpenClaw Skill on EC2

```bash
# Copy skill to OpenClaw's skill directory
# Adjust path to match your OpenClaw installation
cp -r /home/ubuntu/claudebridge/openclaw-skill/ ~/.openclaw/skills/claudebridge/
cd ~/.openclaw/skills/claudebridge/
npm install

# Restart OpenClaw to load the new skill
# (command depends on how you run OpenClaw — systemd, pm2, docker, etc.)
```

Test in Telegram:
```
/claude status
```
Should respond with "No pending questions. Relay: not connected yet."

### Step 3: Start Relay as a Service

```bash
# Copy systemd service
sudo cp /home/ubuntu/claudebridge/claudebridge.service /etc/systemd/system/
sudo systemctl enable claudebridge
sudo systemctl start claudebridge

# Verify
sudo systemctl status claudebridge
curl http://localhost:8400/api/status
```

`claudebridge.service`:
```ini
[Unit]
Description=ClaudeBridge Relay Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/claudebridge/relay
ExecStart=/home/ubuntu/claudebridge/relay/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8400
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Step 4: Update SSH Tunnel on Desktop

Update your tunnel command to include port 8400:

```powershell
ssh -i F:\work\OpenClaw\Bot1\clawed1.pem -N -L 18789:127.0.0.1:18789 -L 8400:127.0.0.1:8400 ubuntu@3.101.144.251
```

Or use the provided `tunnel.ps1` script.

Verify the tunnel works:
```powershell
curl http://localhost:8400/api/status
```

### Step 5: Configure Claude Code Hooks on Desktop

Add to `~/.claude/settings.json`:

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

### Step 6: Test End-to-End

On desktop:
```powershell
python G:\work\ClaudeBridge\scripts\test_flow.py
```

This sends a fake permission request to `localhost:8400` → tunnels to EC2 → relay → OpenClaw → Telegram.

Reply "yes" in Telegram → OpenClaw skill → relay → tunnel → test script confirms round-trip.

---

## 7. Failure Modes and Edge Cases

| Scenario | Behavior |
|----------|----------|
| **SSH tunnel not running** | Claude Code hook gets connection refused on localhost:8400 → fails silently → Claude Code works normally with on-screen prompts |
| **SSH tunnel drops mid-question** | Long-poll HTTP request breaks → Claude Code hook gets error → proceeds with default | 
| **EC2 relay is down** | Same as tunnel not running from desktop perspective |
| **OpenClaw is down** | Relay stores question, can't notify skill → question sits pending → timeout |
| **Telegram unreachable** | OpenClaw can't deliver → relay retries 3x → timeout |
| **No reply in time** | Relay returns timeout response → hook gets default deny/skip |
| **Multiple questions queue** | Each gets unique ID → Telegram shows in order → reply to any |
| **Reply after timeout** | Relay discards → Telegram gets "⏱️ Expired" |
| **Desktop sleeps** | Tunnel drops → in-flight questions timeout → on wake, reconnect tunnel, resume |
| **EC2 reboots** | systemd restarts relay → tunnel reconnects → resume |
| **User sends reply but tunnel is down** | Relay receives reply from OpenClaw, stores it → but no HTTP connection waiting → reply stored but unused → next session can check for stale replies |

### Graceful Degradation Guarantee

If any part of ClaudeBridge is down (tunnel, relay, OpenClaw, Telegram), Claude Code continues working exactly as it does today — with on-screen prompts in VS Code. ClaudeBridge is purely additive.

---

## 8. Security Considerations

- **Relay binds to 127.0.0.1 only** — not accessible from the internet, only via SSH tunnel
- **No new EC2 ports exposed** — everything goes through your existing SSH connection
- **SSH tunnel provides encryption** — same security as your current OpenClaw access
- **No auth tokens needed** — the SSH key IS the authentication
- **No credentials pass through the relay** — only question text and project/file context
- **Telegram messages show project and file names** — acceptable since it's your private channel
- **Config file gitignored** — no secrets in repo

### .gitignore

```
relay/config.yaml
relay/data/
relay/logs/
*.log
*.db
__pycache__/
venv/
node_modules/
```

---

## 9. Future Enhancements

### Phase 2: Auto-Pilot Rules

Define rules on EC2 so routine operations auto-approve without hitting Telegram:

```yaml
# In relay/config.yaml
auto_rules:
  - match: "npm test"
    action: "approve"
  - match: "npm run lint"
    action: "approve"
  - match: "npm run build"
    action: "approve"
  - match: "git add"
    action: "approve"
  - match: "rm -rf"
    action: "deny"
  - match: "git push.*--force"
    action: "deny"
  - match: "git push"
    action: "ask"         # Always ask for pushes
  - match: ".*\\.env.*"
    action: "ask"         # Always ask for .env file edits
```

Evaluated by the relay before notifying OpenClaw. Matching questions get instant responses without Telegram round-trip.

### Phase 3: Inline Question Capture

Capture Claude Code's free-form conversational questions:

- **Option A:** VS Code extension companion that watches the Claude Code panel for input-waiting states
- **Option B:** Claude Code `--output-format json` mode with a stream parser
- **Option C:** A CLAUDE.md instruction telling Claude Code to POST questions to a URL before asking inline

### Phase 4: Rich Mobile Interactions

- **Code diffs:** Send formatted snippets to Telegram for mobile review
- **Voice replies:** OpenClaw transcribes voice memos → relay forwards as text
- **Photos:** Send screenshots from phone → context for Claude Code

### Phase 5: Multi-Project

- Tag questions with project name in Telegram messages
- `/claude filter rivvex` — only show Rivvex questions
- Separate Telegram forum topics per project

### Phase 6: Metrics Dashboard

Simple web page on EC2 (add another SSH tunnel port) showing:
- Questions asked / answered / timed out
- Average response time
- Most common commands approved/denied
- Session history

---

## 10. Dependencies

### Relay Service (Python — EC2)

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.110 | HTTP server |
| uvicorn | >=0.27 | ASGI server |
| aiohttp | >=3.9 | Async HTTP to notify OpenClaw |
| aiosqlite | >=0.19 | Async SQLite |
| pyyaml | >=6.0 | Config parsing |
| pydantic | >=2.0 | Data validation (bundled with FastAPI) |

### OpenClaw Skill (Node.js — EC2)

| Package | Version | Purpose |
|---------|---------|---------|
| axios | >=1.6 | HTTP client to call relay API |

### Infrastructure (all existing)

| Requirement | Status |
|-------------|--------|
| AWS EC2 instance | ✅ Already running (3.101.144.251) |
| SSH key | ✅ F:\work\OpenClaw\Bot1\clawed1.pem |
| OpenClaw on EC2 | ✅ Already running with Telegram |
| Python 3.10+ on EC2 | ✅ Likely already installed |
| Claude Code CLI on desktop | ✅ Just installed |
| Git for Windows | ✅ Installed |

**New infrastructure needed: none.**

---

## 11. Success Criteria

1. ✅ `curl http://localhost:8400/api/status` returns healthy (through tunnel)
2. ✅ `/claude status` in Telegram responds correctly
3. ✅ Claude Code permission request appears in Telegram within 5 seconds
4. ✅ Reply on Telegram reaches Claude Code within 5 seconds
5. ✅ Quick replies (yes/no) work without `/claude` prefix
6. ✅ Timeout returns default deny — Claude Code continues
7. ✅ Tunnel drop = Claude Code works normally (graceful degradation)
8. ✅ EC2 reboot = relay auto-restarts via systemd
9. ✅ Relay runs 24+ hours without issues
10. ✅ Full setup takes under 20 minutes

---

## 12. Implementation Priority

Build and test in this order:

1. **Relay core** — `main.py`, `models.py`, `queue_manager.py` — POST question, long-poll, POST reply
2. **Test relay standalone** — curl commands on EC2 to verify question → reply flow
3. **OpenClaw skill** — notification formatting + reply capture
4. **Test relay + skill** — verify Telegram round-trip on EC2
5. **Tunnel setup** — add port 8400 to SSH command
6. **Claude Code hooks** — configure and test with real Claude Code session
7. **Polish** — systemd service, error handling, logging, convenience scripts
