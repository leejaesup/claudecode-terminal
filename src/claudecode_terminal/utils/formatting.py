"""Message formatting and splitting utilities for Telegram."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from claudecode_terminal.storage.models import ExecutionResult

if TYPE_CHECKING:
    from telegram import Update

logger = logging.getLogger(__name__)

MAX_TELEGRAM_LENGTH = 4096
FILE_THRESHOLD = 50000


def split_message(text: str, max_len: int = MAX_TELEGRAM_LENGTH) -> list[str]:
    """Split a long message into chunks respecting Telegram's character limit."""
    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to split at a newline
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def format_duration(ms: int) -> str:
    """Format milliseconds to human-readable duration."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        minutes = ms // 60000
        seconds = (ms % 60000) // 1000
        return f"{minutes}m {seconds}s"


def format_claude_result(result: ExecutionResult, project: str) -> str:
    """Format Claude Code execution result."""
    output = result.stdout or result.stderr or "(no output)"
    elapsed = format_duration(result.execution_time_ms)
    return f"Claude | {project} | {elapsed}\n\n{output}"


def format_shell_result(result: ExecutionResult, command: str) -> str:
    """Format shell command execution result."""
    if result.blocked:
        return f"Blocked: {result.reason}"

    output = result.stdout or result.stderr or "(no output)"
    icon = "OK" if result.exit_code == 0 else f"ERR({result.exit_code})"
    return f"$ {command}\n[{icon}]\n\n{output}"


async def send_long_message(update: Update, text: str) -> None:
    """Send a message, splitting or sending as file if too long."""
    if not update.message:
        return

    if len(text) <= MAX_TELEGRAM_LENGTH:
        await update.message.reply_text(text)
    elif len(text) <= FILE_THRESHOLD:
        for chunk in split_message(text):
            await update.message.reply_text(chunk)
    else:
        # Send as file for very long output
        file = io.BytesIO(text.encode("utf-8"))
        file.name = "output.txt"
        await update.message.reply_document(file, caption="Output too long, sent as file.")
