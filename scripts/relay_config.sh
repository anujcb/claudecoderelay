#!/bin/bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SKILL_DIR/config.yaml"

if [ -z "$1" ]; then
    python3 -c "
import yaml, json
with open('$CONFIG') as f:
    d = yaml.safe_load(f)
if 'telegram' in d and 'bot_token' in d['telegram']:
    d['telegram']['bot_token'] = '***REDACTED***'
print(json.dumps(d, indent=2))
"
    exit 0
fi

KEY="$1"
VALUE="$2"

if [ -z "$VALUE" ]; then
    echo '{"error":"Usage: relay_config.sh <key> <value>. Keys: chat_id, timeout, timeout_action, port"}'
    exit 1
fi

python3 -c "
import yaml, json

with open('$CONFIG') as f:
    d = yaml.safe_load(f)

key = '$KEY'
value = '$VALUE'

if key == 'chat_id':
    d['telegram']['chat_id'] = value
elif key == 'timeout':
    d['timeouts']['default_seconds'] = int(value)
elif key == 'timeout_action':
    d['defaults']['timeout_action'] = value
elif key == 'port':
    d['server']['port'] = int(value)
else:
    print(json.dumps({'error': 'Unknown key: ' + key}))
    exit(1)

with open('$CONFIG', 'w') as f:
    yaml.dump(d, f, default_flow_style=False)

print(json.dumps({'status': 'updated', 'key': key, 'note': 'Restart relay for changes to take effect.'}))"
