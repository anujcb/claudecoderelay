"""
End-to-end test: simulate a Claude Code hook sending a question through the tunnel.

Run from desktop:
    python G:\\work\\ClaudeBridge\\scripts\\test_flow.py

Expects:
  - SSH tunnel running (localhost:8400 -> EC2:8400)
  - ClaudeBridge relay running on EC2
  - OpenClaw skill installed and OpenClaw running

The script sends a fake permission request, then waits for you to reply
via Telegram. It prints the reply when received.
"""

import json
import sys
import time

import urllib.request
import urllib.error

RELAY_URL = "http://localhost:8400"


def check_status():
    """Quick health check."""
    try:
        req = urllib.request.Request(f"{RELAY_URL}/api/status")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            print(f"  Relay status: {data.get('status')}")
            print(f"  Uptime: {data.get('uptime_seconds', 0)}s")
            return True
    except urllib.error.URLError as e:
        print(f"  ERROR: Cannot reach relay at {RELAY_URL}")
        print(f"  Is the SSH tunnel running? Error: {e}")
        return False


def send_test_question():
    """Send a fake permission request and wait for reply (long-poll)."""
    payload = json.dumps({
        "hook_type": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "echo 'Hello from ClaudeBridge test!'"},
        "session_id": "test-session-001",
        "project": "ClaudeBridge-Test",
    }).encode()

    req = urllib.request.Request(
        f"{RELAY_URL}/api/question",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    print("\n  Waiting for your reply on Telegram...")
    print("  (This will long-poll for up to 30 minutes)\n")

    try:
        # Long timeout — we're waiting for a human reply
        with urllib.request.urlopen(req, timeout=1860) as resp:
            data = json.loads(resp.read())
            return data
    except urllib.error.URLError as e:
        print(f"  ERROR: Request failed: {e}")
        return None
    except TimeoutError:
        print("  Timed out waiting for reply.")
        return None


def main():
    print("=" * 50)
    print("ClaudeBridge End-to-End Test")
    print("=" * 50)

    print("\n[1] Checking relay status...")
    if not check_status():
        sys.exit(1)

    print("\n[2] Sending test question to relay...")
    print("    Tool: Bash")
    print("    Command: echo 'Hello from ClaudeBridge test!'")

    start = time.time()
    result = send_test_question()
    elapsed = time.time() - start

    if result:
        print(f"\n[3] Reply received in {elapsed:.1f}s!")
        print(f"    Decision: {result.get('decision')}")
        print(f"    Reason: {result.get('reason')}")
        print("\n  SUCCESS — Full round-trip works!")
    else:
        print("\n[3] No reply received.")
        print("  Check: Is OpenClaw running? Did the Telegram message appear?")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
