"""Tests for shell executor service."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claudecode_terminal.config import AppConfig, BotConfig, ClaudeConfig, ShellConfig, StorageConfig, LoggingConfig
from claudecode_terminal.services.shell import ShellRunner


@pytest.fixture
def shell_config(tmp_path):
    project_dir = tmp_path / "projects"
    project_dir.mkdir(parents=True)
    return AppConfig(
        bot=BotConfig(token="test"),
        claude=ClaudeConfig(default_project=str(project_dir), max_output=4096),
        shell=ShellConfig(timeout=5, enabled=True),
        storage=StorageConfig(db_path=str(tmp_path / "test.db")),
        logging=LoggingConfig(),
    )


@pytest.fixture
def runner(shell_config):
    return ShellRunner(shell_config)


class TestShellRunner:
    @pytest.mark.asyncio
    async def test_execute_blacklisted_fork_bomb(self, runner):
        result = await runner.execute(":(){ :|:& };:", user_id="123")
        assert result.blocked
        assert "Fork bomb" in result.reason

    @pytest.mark.asyncio
    async def test_execute_blacklisted_rm_rf(self, runner):
        result = await runner.execute("rm -rf /", user_id="123")
        assert result.blocked

    @pytest.mark.asyncio
    async def test_execute_success(self, runner, shell_config):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"file1.txt\nfile2.txt\n", b""))
        mock_proc.returncode = 0

        with patch("claudecode_terminal.services.shell.asyncio.create_subprocess_shell", return_value=mock_proc):
            with patch("claudecode_terminal.services.shell.save_command", new_callable=AsyncMock):
                result = await runner.execute("ls", user_id="123", cwd=shell_config.claude.default_project)
        assert result.exit_code == 0
        assert "file1.txt" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_timeout(self, runner, shell_config):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=[asyncio.TimeoutError, (b"", b"")])
        mock_proc.kill = MagicMock()

        with patch("claudecode_terminal.services.shell.asyncio.create_subprocess_shell", return_value=mock_proc):
            with patch("claudecode_terminal.services.shell.save_command", new_callable=AsyncMock):
                result = await runner.execute("sleep 100", user_id="123", cwd=shell_config.claude.default_project)
        assert result.exit_code == -1
        assert "timed out" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_execute_shell_disabled(self, shell_config):
        shell_config.shell.enabled = False
        runner = ShellRunner(shell_config)
        result = await runner.execute("ls", user_id="123")
        assert result.blocked
        assert "disabled" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_safe_command_not_blocked(self, runner):
        # This won't actually execute - just verifying the blacklist doesn't block it
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))
        mock_proc.returncode = 0

        with patch("claudecode_terminal.services.shell.asyncio.create_subprocess_shell", return_value=mock_proc):
            with patch("claudecode_terminal.services.shell.save_command", new_callable=AsyncMock):
                result = await runner.execute("git status", user_id="123")
        assert not result.blocked
        assert result.exit_code == 0
