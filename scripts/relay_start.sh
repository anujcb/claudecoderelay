#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SKILL_DIR/config.yaml"
PID_FILE="$SKILL_DIR/data/relay.pid"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo '{"status":"already_running","pid":'$(cat "$PID_FILE")'}'
    exit 0
fi

source "$SKILL_DIR/.venv/bin/activate"

PORT=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    print(yaml.safe_load(f)['server']['port'])
" 2>/dev/null || echo "8400")

mkdir -p "$SKILL_DIR/data" "$SKILL_DIR/logs"

nohup python3 -m uvicorn relay.main:app \
    --host 127.0.0.1 \
    --port "$PORT" \
    --app-dir "$SKILL_DIR" \
    > "$SKILL_DIR/logs/relay.log" 2>&1 &

echo $! > "$PID_FILE"
sleep 1

if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "{\"status\":\"started\",\"pid\":$(cat "$PID_FILE"),\"port\":$PORT}"
else
    echo '{"status":"failed","error":"Process exited immediately. Check logs/relay.log"}'
    exit 1
fi
