"""System utility checks."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def check_claude_cli() -> tuple[bool, str]:
    """Check if Claude Code CLI is installed and return version."""
    claude_path = shutil.which("claude")
    if not claude_path:
        return False, "Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip()
        return True, version
    except subprocess.TimeoutExpired:
        return False, "Claude CLI version check timed out"
    except Exception as e:
        return False, f"Error checking Claude CLI: {e}"


def check_project_dir(path: str) -> tuple[bool, str]:
    """Validate a project directory path."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        return False, f"Directory not found: {resolved}"
    if not resolved.is_dir():
        return False, f"Not a directory: {resolved}"
    return True, str(resolved)
