"""Command blacklist checker - shared across layers."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

BLACKLIST_PATTERNS: list[tuple[str, str]] = [
    (r":\(\)\s*\{\s*:\|:\s*&\s*\}", "Fork bomb detected"),
    (r"\brm\s+(-[rfRF]+\s+)?/\s*$", "Dangerous rm on root"),
    (r"\bmkfs\b", "Filesystem format blocked"),
    (r"\bdd\s+if=", "Raw disk write blocked"),
    (r"^(shutdown|reboot|halt|poweroff)\b", "System control blocked"),
    (
        r"^(vi|vim|nvim|nano|emacs|pico|less|more|top|htop|man|ssh|ftp|telnet|mysql|psql|mongo|python3?|node|irb|bash|zsh|sh|csh)\b",
        "Interactive command not supported. Use /shell with non-interactive commands.",
    ),
]


class BlacklistChecker:
    """Regex-based command blacklist checker."""

    def __init__(self) -> None:
        self._patterns: list[tuple[re.Pattern[str], str]] = []
        for pattern, reason in BLACKLIST_PATTERNS:
            try:
                self._patterns.append((re.compile(pattern, re.IGNORECASE), reason))
            except re.error:
                logger.error("Invalid blacklist pattern: %s", pattern)

    def check(self, command: str) -> tuple[bool, str]:
        """Check if a command is blacklisted. Returns (blocked, reason)."""
        for compiled, reason in self._patterns:
            if compiled.search(command):
                logger.warning("Blacklisted command: %s (reason: %s)", command, reason)
                return True, reason
        return False, ""


blacklist_checker = BlacklistChecker()
