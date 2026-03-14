#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$SKILL_DIR/data/relay.pid"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    kill "$(cat "$PID_FILE")"
    rm "$PID_FILE"
    echo '{"status":"stopped"}'
else
    rm -f "$PID_FILE"
    echo '{"status":"not_running"}'
fi
