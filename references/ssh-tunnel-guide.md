# SSH Tunnel Setup for Claude Code Relay

## Quick Setup

Add port 8400 to your existing SSH tunnel command:

```bash
ssh -i /path/to/key.pem -N \
    -L 8400:127.0.0.1:8400 \
    user@your-server-ip
```

If you already tunnel other ports (e.g. 18789 for OpenClaw control panel), combine them:

```bash
ssh -i /path/to/key.pem -N \
    -L 18789:127.0.0.1:18789 \
    -L 8400:127.0.0.1:8400 \
    user@your-server-ip
```

## Keep-Alive Options

Add these flags to prevent tunnel drops:

```
-o ServerAliveInterval=60
-o ServerAliveCountMax=3
```

This sends a keepalive every 60 seconds and disconnects after 3 missed replies (3 minutes).

## Verify Tunnel

From your desktop:

```bash
curl http://localhost:8400/api/status
```

Should return JSON with `"status": "running"`.

## If Tunnel Drops

Claude Code works normally — hooks fail silently and you get on-screen prompts as usual. Restart the tunnel and the relay will resume accepting questions.

## PowerShell Convenience Scripts

See `scripts/tunnel.ps1` and `scripts/tunnel-persistent.ps1` for Windows convenience scripts with auto-reconnect.
