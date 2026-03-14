#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SKILL_DIR/config.yaml"

PORT=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    print(yaml.safe_load(f)['server']['port'])
" 2>/dev/null || echo "8400")

COUNT="${1:-10}"

curl -s "http://localhost:$PORT/api/history?count=$COUNT" 2>/dev/null || \
    echo '{"error":"Relay not running."}'
