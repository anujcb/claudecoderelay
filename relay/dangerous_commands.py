"""Dangerous command pattern matching for Claude Code Relay."""

from __future__ import annotations

import re

DANGEROUS_PATTERNS = [
    r"rm\s+-rf",
    r"git\s+push.*--force",
    r"git\s+reset\s+--hard",
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
    r"truncate\s+",
    r"\.env",
    r"password|secret|token|key",
    r"sudo\s+",
    r"chmod\s+777",
    r"curl.*\|\s*(ba)?sh",
    r"format\s+[a-z]:",
    r"mkfs\.",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]


def is_dangerous(text: str | None) -> bool:
    """Check if text matches any dangerous command pattern."""
    if not text:
        return False
    return any(p.search(text) for p in _compiled)
