"""Parse Claude Code HTTP hook payloads into internal Question objects."""

from __future__ import annotations

import json
import logging

from .models import HookPayload, Question

logger = logging.getLogger("claudecoderelay.parser")


def parse_hook(payload: dict) -> Question:
    """Convert a raw Claude Code hook payload into a Question."""
    hook = HookPayload.model_validate(payload)

    tool_input_str = None
    if hook.tool_input is not None:
        tool_input_str = (
            json.dumps(hook.tool_input)
            if isinstance(hook.tool_input, dict)
            else str(hook.tool_input)
        )

    formatted = _format_question(hook)

    return Question(
        hook_type=hook.hook_type,
        tool_name=hook.tool_name,
        tool_input=tool_input_str,
        formatted_question=formatted,
    )


def _format_question(hook: HookPayload) -> str:
    """Create a human-readable question string from hook data."""
    if hook.hook_type == "Stop":
        return "Session ended"

    tool = hook.tool_name or "unknown tool"

    if hook.tool_input and isinstance(hook.tool_input, dict):
        if tool.lower() == "bash" and "command" in hook.tool_input:
            return hook.tool_input["command"]
        if "file_path" in hook.tool_input:
            return hook.tool_input["file_path"]
        return f"{tool}: {json.dumps(hook.tool_input, indent=None)[:200]}"

    return tool
