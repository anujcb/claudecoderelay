"""Format messages for Telegram notifications."""

from __future__ import annotations

from .dangerous_commands import is_dangerous
from .models import Question


def format_question(question: Question) -> str:
    """Format a question for Telegram notification."""
    short_id = question.short_id
    tool = question.tool_name or ""
    tool_input = question.tool_input or ""
    formatted = question.formatted_question or f"{tool}: {tool_input}"
    timeout_min = question.timeout_seconds // 60
    dangerous = is_dangerous(tool_input) or is_dangerous(formatted)

    if question.hook_type == "Stop":
        return (
            f"✅ Claude Code [{short_id}]\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Session ended."
        )

    header = f"🔴 Claude Code [{short_id}]" if dangerous else f"🤖 Claude Code [{short_id}]"
    lines = [
        header,
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    # Tool-specific formatting
    if tool.lower() == "bash":
        cmd = _extract_command(tool_input)
        lines.append(f"🔧 Run: {cmd}")
    elif tool.lower() in ("edit", "write"):
        path = _extract_file_path(tool_input)
        lines.append(f"📝 Edit: {path}")
    elif tool.lower() == "read":
        path = _extract_file_path(tool_input)
        lines.append(f"📖 Read: {path}")
    else:
        lines.append(f"🔧 {formatted}")

    if dangerous:
        warning = _get_danger_warning(tool_input, formatted)
        lines.append("")
        lines.append(f"⚠️ {warning}")

    lines.append("")
    lines.append("Reply in OpenClaw: approve or deny")
    lines.append(f"⏱️ {timeout_min} min timeout")

    return "\n".join(lines)


def format_approval(question: Question) -> str:
    """Format an approval confirmation."""
    short = question.formatted_question or question.tool_name or "unknown"
    return f"✅ Approved [{question.short_id}]: {short}"


def format_denial(question: Question) -> str:
    """Format a denial confirmation."""
    short = question.formatted_question or question.tool_name or "unknown"
    return f"❌ Denied [{question.short_id}]: {short}"


def format_timeout(question: Question, default_action: str) -> str:
    """Format a timeout notification."""
    short = question.formatted_question or question.tool_name or "unknown"
    return (
        f"⏱️ Timed out [{question.short_id}]: {short}\n"
        f"Default: {default_action}"
    )


def format_relay_started(port: int) -> str:
    return (
        f"🔌 Claude Code Relay started\n"
        f"Ready to receive questions on port {port}."
    )


def format_relay_stopped() -> str:
    return "🔌 Claude Code Relay stopped"


def _extract_command(tool_input: str) -> str:
    if not tool_input:
        return "unknown"
    try:
        import json
        parsed = json.loads(tool_input)
        return parsed.get("command", str(parsed))[:200]
    except (json.JSONDecodeError, TypeError):
        return str(tool_input)[:200]


def _extract_file_path(tool_input: str) -> str:
    if not tool_input:
        return "unknown"
    try:
        import json
        parsed = json.loads(tool_input)
        return parsed.get("file_path", parsed.get("path", str(parsed)))[:200]
    except (json.JSONDecodeError, TypeError):
        return str(tool_input)[:200]


def _get_danger_warning(tool_input: str, formatted: str) -> str:
    combined = f"{tool_input} {formatted}".lower()
    if "force" in combined and "push" in combined:
        return "FORCE PUSH — review carefully!"
    if "rm -rf" in combined or "rm -r" in combined:
        return "RECURSIVE DELETE — review carefully!"
    if "reset --hard" in combined:
        return "HARD RESET — review carefully!"
    if "drop" in combined:
        return "DATABASE DROP — review carefully!"
    if "sudo" in combined:
        return "SUDO command — review carefully!"
    return "Potentially dangerous — review carefully!"
