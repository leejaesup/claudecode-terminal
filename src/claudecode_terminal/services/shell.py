"""Shell command executor service."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from claudecode_terminal.services.blacklist import blacklist_checker
from claudecode_terminal.config import AppConfig
from claudecode_terminal.storage.database import save_command
from claudecode_terminal.storage.models import ExecutionResult

logger = logging.getLogger(__name__)


class ShellRunner:
    """Execute shell commands with blacklist and timeout protection."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def execute(
        self,
        command: str,
        user_id: str,
        cwd: str | None = None,
    ) -> ExecutionResult:
        """Execute a shell command."""
        if not self.config.shell.enabled:
            return ExecutionResult(
                stderr="Shell commands are disabled in configuration.",
                exit_code=-1,
                blocked=True,
                reason="Shell disabled",
            )

        # Blacklist check
        blocked, reason = blacklist_checker.check(command)
        if blocked:
            return ExecutionResult(
                stderr=f"Blocked: {reason}",
                exit_code=-1,
                blocked=True,
                reason=reason,
            )

        # Resolve working directory
        work_dir = cwd or self.config.claude.default_project
        work_dir = str(Path(work_dir).expanduser().resolve())

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.shell.timeout,
            )
            exit_code = proc.returncode or 0
        except asyncio.TimeoutError:
            proc.kill()  # type: ignore[possibly-undefined]
            await proc.communicate()
            stdout_bytes = b""
            stderr_bytes = f"Command timed out after {self.config.shell.timeout}s".encode()
            exit_code = -1
        except Exception as e:
            logger.exception("Shell execution error")
            stdout_bytes = b""
            stderr_bytes = str(e).encode()
            exit_code = -1

        elapsed_ms = int((time.monotonic() - start) * 1000)
        max_out = self.config.claude.max_output
        stdout = stdout_bytes.decode("utf-8", errors="replace")[:max_out]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:max_out]

        await save_command(
            user_id=user_id,
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=elapsed_ms,
            source="telegram",
        )

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=elapsed_ms,
        )
