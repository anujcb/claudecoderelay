#!/bin/bash
set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RELAY_DIR="$SKILL_DIR/relay"
CONFIG_FILE="$SKILL_DIR/config.yaml"

echo "🔌 Claude Code Relay — Setup"
echo "═══════════════════════════"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 required. Install it first."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
python3 -m venv "$SKILL_DIR/.venv" 2>/dev/null || true
source "$SKILL_DIR/.venv/bin/activate"
pip install -q -r "$RELAY_DIR/requirements.txt"

# Create config
if [ ! -f "$CONFIG_FILE" ]; then
    # Try to read bot token from OpenClaw config
    BOT_TOKEN=""
    OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
    if [ -f "$OPENCLAW_CONFIG" ]; then
        BOT_TOKEN=$(python3 -c "
import json
with open('$OPENCLAW_CONFIG') as f:
    d = json.load(f)
def find_token(obj):
    if isinstance(obj, dict):
        if 'botToken' in obj:
            return obj['botToken']
        for v in obj.values():
            r = find_token(v)
            if r: return r
    if isinstance(obj, list):
        for v in obj:
            r = find_token(v)
            if r: return r
    return None
print(find_token(d) or '')
" 2>/dev/null)
    fi

    if [ -n "$BOT_TOKEN" ]; then
        echo "✅ Found bot token from OpenClaw config."
    else
        echo ""
        echo "Could not find bot token automatically."
        read -p "Paste your OpenClaw Telegram bot token: " BOT_TOKEN
    fi

    # Get chat ID from OpenClaw credentials
    CHAT_ID=""
    ALLOW_FILE="$HOME/.openclaw/credentials/telegram-default-allowFrom.json"
    if [ -f "$ALLOW_FILE" ]; then
        CHAT_ID=$(python3 -c "
import json
with open('$ALLOW_FILE') as f:
    d = json.load(f)
ids = d.get('allowFrom', [])
if ids:
    print(ids[0])
" 2>/dev/null)
    fi

    if [ -n "$CHAT_ID" ]; then
        echo "✅ Found chat ID from OpenClaw credentials: $CHAT_ID"
    else
        read -p "Your Telegram chat ID: " CHAT_ID
    fi

    read -p "Relay port (default 8400): " PORT
    PORT=${PORT:-8400}

    cat > "$CONFIG_FILE" <<EOF
server:
  host: "127.0.0.1"
  port: $PORT

telegram:
  bot_token: "$BOT_TOKEN"
  chat_id: "$CHAT_ID"

timeouts:
  default_seconds: 1800
  max_seconds: 7200
  expiry_check_seconds: 30

defaults:
  timeout_action: "deny"

logging:
  level: "INFO"
  file: "logs/relay.log"
EOF

    echo "✅ Config saved."
fi

# Create data/logs dirs
mkdir -p "$SKILL_DIR/data" "$SKILL_DIR/logs"

# Print desktop instructions
PORT=$(python3 -c "
import yaml
with open('$CONFIG_FILE') as f:
    print(yaml.safe_load(f)['server']['port'])
" 2>/dev/null || echo "8400")

echo ""
echo "═══════════════════════════════════════════"
echo "🖥️  DO THIS ON YOUR DESKTOP"
echo "═══════════════════════════════════════════"
echo ""
echo "1. Add port $PORT to your SSH tunnel:"
echo "   ssh -i /path/to/key.pem -N \\"
echo "       -L $PORT:127.0.0.1:$PORT \\"
echo "       [your existing tunnel flags] \\"
echo "       user@your-server"
echo ""
echo "2. Add to ~/.claude/settings.json on your desktop:"
echo '   {'
echo '     "hooks": {'
echo '       "PreToolUse": [{'
echo '         "type": "http",'
echo "         \"url\": \"http://localhost:$PORT/api/question\""
echo '       }]'
echo '     }'
echo '   }'
echo ""
echo "3. Tell me: 'start claude code relay'"
echo ""
echo "✅ Setup complete!"
