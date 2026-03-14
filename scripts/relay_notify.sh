#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SKILL_DIR/config.yaml"

MESSAGE="$1"

if [ -z "$MESSAGE" ]; then
    echo '{"error":"Usage: relay_notify.sh <message>"}'
    exit 1
fi

BOT_TOKEN=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    print(yaml.safe_load(f)['telegram']['bot_token'])
")

CHAT_ID=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    print(yaml.safe_load(f)['telegram']['chat_id'])
")

curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
    -H "Content-Type: application/json" \
    -d "{\"chat_id\": \"$CHAT_ID\", \"text\": \"$MESSAGE\", \"parse_mode\": \"HTML\"}" \
    2>/dev/null
