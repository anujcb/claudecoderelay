#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SKILL_DIR/config.yaml"

PORT=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    print(yaml.safe_load(f)['server']['port'])
" 2>/dev/null || echo "8400")

QUESTION_ID="$1"
DECISION="$2"

if [ -z "$QUESTION_ID" ] || [ -z "$DECISION" ]; then
    echo '{"error":"Usage: relay_reply.sh <question_id> <approve|deny|text>"}'
    exit 1
fi

curl -s -X POST "http://localhost:$PORT/api/reply/$QUESTION_ID" \
    -H "Content-Type: application/json" \
    -d "{\"reply\": \"$DECISION\"}" 2>/dev/null || \
    echo '{"error":"Relay not running."}'
