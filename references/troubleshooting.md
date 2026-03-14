# Troubleshooting Claude Code Relay

## Relay won't start

1. Check logs: `cat logs/relay.log`
2. Check if port 8400 is already in use: `lsof -i :8400`
3. Check Python venv: `source .venv/bin/activate && python -c "import fastapi"`
4. Re-run setup: `bash scripts/setup.sh`

## No Telegram notifications

1. Check config: `bash scripts/relay_config.sh` — verify bot_token and chat_id
2. Test manually: `bash scripts/relay_notify.sh "test message"`
3. Check relay logs for Telegram API errors

## Replies not reaching Claude Code

1. Verify relay is running: `bash scripts/relay_status.sh`
2. Check pending questions: `bash scripts/relay_pending.sh`
3. Test reply manually: `bash scripts/relay_reply.sh <question_id> approve`
4. Check that the SSH tunnel is active on desktop

## Tunnel issues

1. Verify: `curl http://localhost:8400/api/status` from desktop
2. If connection refused: tunnel is down, restart it
3. If timeout: check firewall or security group settings
4. Add `-v` to SSH command for verbose debugging

## Claude Code hooks not firing

1. Check `~/.claude/settings.json` has the hook configured
2. Verify hook URL is `http://localhost:8400/api/question`
3. Check that tunnel is forwarding port 8400
4. Look at relay logs for incoming requests

## Questions timing out

1. Default timeout is 30 minutes — adjust via: `bash scripts/relay_config.sh timeout 3600`
2. Restart relay after config changes
3. Check that OpenClaw agent is recognizing your replies

## Stale PID file

If relay shows as running but isn't responding:
```bash
rm data/relay.pid
bash scripts/relay_start.sh
```
