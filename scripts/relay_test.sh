#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SKILL_DIR/config.yaml"

PORT=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    print(yaml.safe_load(f)['server']['port'])
" 2>/dev/null || echo "8400")

# Check if relay is running
STATUS=$(curl -s "http://localhost:$PORT/api/status" 2>/dev/null)
if [ $? -ne 0 ]; then
    echo '{"error":"Relay not running. Start it first."}'
    exit 1
fi

# Send test notification
bash "$(dirname "$0")/relay_notify.sh" "🧪 Claude Code Relay — Test
━━━━━━━━━━━━━━━━━━━━
This is a test notification.
If you see this, outbound messaging works.

Now say 'approve' to test the reply flow."

# Create a test question
RESULT=$(curl -s -X POST "http://localhost:$PORT/api/test" 2>/dev/null)
echo "$RESULT"
