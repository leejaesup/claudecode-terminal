"""Data models for claudecode-terminal."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Result from command execution (Claude or shell)."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: int = 0
    blocked: bool = False
    reason: str = ""


@dataclass
class CommandRecord:
    """A stored command history entry."""

    id: int = 0
    user_id: str = ""
    command: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: int = 0
    source: str = "telegram"
    created_at: str = ""
