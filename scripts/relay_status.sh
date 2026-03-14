#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SKILL_DIR/config.yaml"

PORT=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    print(yaml.safe_load(f)['server']['port'])
" 2>/dev/null || echo "8400")

curl -s "http://localhost:$PORT/api/status" 2>/dev/null || \
    echo '{"status":"not_running","message":"Relay is not running. Say start claude code relay."}'
