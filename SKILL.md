---
name: claudecoderelay
description: >
  Remote control for Claude Code via OpenClaw. Receive Claude Code's
  permission requests and questions in your chat. Reply naturally and
  Claude Code continues working on your desktop. No separate bot needed.
version: 1.0.0
metadata:
  openclaw:
    emoji: "🔌"
    requires:
      bins:
        - python3
        - curl
      anyOf:
        - pip
        - pip3
---

# Claude Code Relay — Remote Control for Claude Code

Control your Claude Code sessions from anywhere through OpenClaw.
When Claude Code needs permission to run a command, edit a file, or
make a decision, the question arrives here. Reply naturally and
Claude Code continues.

Uses your existing OpenClaw bot. No separate Telegram bot needed.

## When to Use This Skill

Use this skill when the user:

- Says "start claude code relay" or "start code relay"
- Says "stop claude code relay" or "stop code relay"
- Says "claude code status" or "code relay status" or "what is claude code doing"
- Says "claude code pending" or "any claude code questions"
- Says "approve" / "yes" / "allow" / "deny" / "no" / "reject" in the context of a pending Claude Code question
- Says "approve claude code" or "deny the claude code request"
- Says "claude code history"
- Says "setup claude code relay" or "configure code relay"
- Says "test claude code relay"
- Says "cancel claude code" or "cancel all claude code questions"

## Understanding the Reply Flow

This is critical. Claude Code Relay does NOT poll Telegram for replies.
YOU (the OpenClaw agent) are the reply mechanism. When the user responds
to a Claude Code question, you recognize it and run the reply script.

Here is how to handle replies:

1. When a question is pending (check with relay_pending.sh), track that
   there is an active Claude Code question.

2. When the user says something that sounds like a reply to a Claude Code
   question — "yes", "approve", "deny", "no", "allow it", "go ahead",
   "reject that", "skip" — treat it as a reply.

3. Map the user's intent:
   - Affirmative (yes, approve, allow, go ahead, do it, ok, sure) → "approve"
   - Negative (no, deny, reject, don't, stop, block) → "deny"
   - Anything else → pass through as free-form reply text

4. Get the question ID from relay_pending.sh (most recent pending question
   if only one, or ask the user which one if multiple).

5. Run relay_reply.sh with the question ID and decision.

6. Confirm to the user that the reply was sent.

## Setup (First Time Only)

When the user asks to set up Claude Code Relay:

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/setup.sh
```

This installs Python dependencies and creates the config file.

The user needs the bot token from OpenClaw's own configuration to
send notifications. The setup script will try to read it from
~/.openclaw/openclaw.json automatically. If it can't, it will prompt.

The user also needs to do two things on their desktop:
1. Add `-L 8400:127.0.0.1:8400` to their SSH tunnel command
2. Add the HTTP hook to their Claude Code settings

The setup script prints these instructions.

## Starting the Relay

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_start.sh
```

Remind the user to make sure their SSH tunnel includes port 8400.

## Stopping the Relay

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_stop.sh
```

## Checking Status

When the user asks about Claude Code status, pending questions, or
what Claude Code is doing:

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_status.sh
```

Returns: relay running/stopped, pending question count, last activity, uptime.

## Listing Pending Questions

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_pending.sh
```

Returns JSON array of pending questions with IDs, timestamps, and commands.

## Sending a Reply

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_reply.sh <question_id> <decision>
```

Where decision is: approve, deny, or free-form text.

If only one question is pending, the user doesn't need to specify the ID.
Get the ID from relay_pending.sh and use it automatically.

## Viewing History

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_history.sh [count]
```

Default: last 10 questions with outcomes.

## Cancelling Questions

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_cancel.sh <question_id|all>
```

## Testing

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_test.sh
```

Sends a test notification to Telegram and creates a test pending question.
Ask the user to approve or deny it to confirm the flow works.

## Updating Configuration

```bash
bash ~/.openclaw/skills/claudecoderelay/scripts/relay_config.sh [key] [value]
```

Without arguments: shows config (secrets redacted).
With arguments: updates a value. Keys: chat_id, timeout, timeout_action, port.

## Notifications

When a new question arrives, the relay sends a notification to Telegram
using OpenClaw's own bot. The agent does not need to do anything for this —
the relay handles outbound notifications directly.

The notification looks like:

```
🤖 Claude Code [abc123]
━━━━━━━━━━━━━━━━━━━━
📁 ProjectName
🔧 Run: npm test

Reply in OpenClaw to approve or deny.
⏱️ 30 min timeout
```

For dangerous commands (rm -rf, git push --force, sudo, etc.):

```
🔴 Claude Code [def456]
━━━━━━━━━━━━━━━━━━━━
📁 ProjectName
🔧 Run: git push --force origin main

⚠️ FORCE PUSH — review carefully!
Reply in OpenClaw to approve or deny.
⏱️ 30 min timeout
```

## Important Notes

- Relay binds to 127.0.0.1 only — not exposed to the internet
- SSH tunnel required to connect user's desktop to the relay
- If tunnel is down, Claude Code works normally (on-screen prompts)
- Claude Code Relay uses OpenClaw's existing bot for notifications
- Replies come through you (the agent), not Telegram polling
- Phase 1 only captures hook events (permission requests)
- Free-form inline questions from Claude Code don't trigger hooks yet
- Remind users: NEVER share bot tokens in chat
