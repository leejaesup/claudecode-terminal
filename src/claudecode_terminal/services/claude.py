"""Claude Code CLI executor service."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from claudecode_terminal.config import MODEL_ALIASES, AppConfig
from claudecode_terminal.storage.database import save_command
from claudecode_terminal.storage.models import ExecutionResult

logger = logging.getLogger(__name__)


class ClaudeRunner:
    """Execute Claude Code CLI commands."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def execute(
        self,
        prompt: str,
        project_path: str,
        user_id: str,
        model: str = "",
        max_turns: int = 0,
        system_prompt: str = "",
        continue_conversation: bool = False,
    ) -> ExecutionResult:
        """Execute a Claude Code CLI command."""
        resolved_path = Path(project_path).expanduser().resolve()
        if not resolved_path.is_dir():
            return ExecutionResult(
                stdout="",
                stderr=f"Project directory not found: {resolved_path}",
                exit_code=-1,
            )

        # Build command args (use exec, not shell, to prevent injection)
        cmd: list[str] = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "text",
            "--dangerously-skip-permissions",
        ]

        if model:
            resolved_model = MODEL_ALIASES.get(model, model)
            cmd.extend(["--model", resolved_model])

        if max_turns > 0:
            cmd.extend(["--max-turns", str(max_turns)])

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        if continue_conversation:
            cmd.append("--continue")

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(resolved_path),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.claude.timeout,
            )
            exit_code = proc.returncode or 0
        except asyncio.TimeoutError:
            proc.kill()  # type: ignore[possibly-undefined]
            await proc.communicate()
            stdout_bytes = b""
            stderr_bytes = f"Claude Code timed out after {self.config.claude.timeout}s".encode()
            exit_code = -1
        except FileNotFoundError:
            return ExecutionResult(
                stdout="",
                stderr="Claude Code CLI not found.\nInstall: npm install -g @anthropic-ai/claude-code",
                exit_code=-1,
            )
        except Exception as e:
            logger.exception("Claude execution error")
            return ExecutionResult(stdout="", stderr=str(e), exit_code=-1)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        max_out = self.config.claude.max_output
        stdout = stdout_bytes.decode("utf-8", errors="replace")[:max_out]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:max_out]

        await save_command(
            user_id=user_id,
            command=f"[claude] {prompt}",
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=elapsed_ms,
            source="claude",
        )

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=elapsed_ms,
        )
