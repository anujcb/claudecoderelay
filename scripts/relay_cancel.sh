#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SKILL_DIR/config.yaml"

PORT=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    print(yaml.safe_load(f)['server']['port'])
" 2>/dev/null || echo "8400")

TARGET="${1:-all}"

curl -s -X DELETE "http://localhost:$PORT/api/question/$TARGET" 2>/dev/null || \
    echo '{"error":"Relay not running."}'
