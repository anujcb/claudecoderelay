# Claude Code HTTP Hook Payload Reference

## Hook Types

Claude Code fires HTTP hooks on lifecycle events:

- **PreToolUse** — Before a tool is executed (permission request)
- **PostToolUse** — After a tool completes
- **Stop** — When session ends

## PreToolUse Payload (expected)

```json
{
  "hook_type": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm test"
  },
  "session_id": "session-uuid"
}
```

## Common tool_name values

- `Bash` — shell command execution
- `Edit` — file editing (tool_input has `file_path`, `old_string`, `new_string`)
- `Write` — file creation (tool_input has `file_path`, `content`)
- `Read` — file reading (tool_input has `file_path`)

## Hook Response Format

The relay returns:

```json
{
  "decision": "approve",
  "reason": "User approved via OpenClaw"
}
```

Or:

```json
{
  "decision": "deny",
  "reason": "User denied via OpenClaw"
}
```

## Important Notes

- The exact payload format should be verified by checking relay logs during first real use
- The relay logs raw payloads at DEBUG level for this purpose
- Hooks only fire on tool use events, not on inline conversational questions
- If the hook endpoint is unreachable, Claude Code proceeds normally
