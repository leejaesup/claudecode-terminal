"""Tests for Claude Code executor service."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from claudecode_terminal.config import AppConfig, BotConfig, ClaudeConfig, ShellConfig, StorageConfig, LoggingConfig
from claudecode_terminal.services.claude import ClaudeRunner
from claudecode_terminal.storage.models import ExecutionResult


@pytest.fixture
def claude_config(tmp_path):
    project_dir = tmp_path / "projects" / "test-project"
    project_dir.mkdir(parents=True)
    return AppConfig(
        bot=BotConfig(token="test"),
        claude=ClaudeConfig(default_project=str(project_dir), timeout=10, max_output=4096),
        shell=ShellConfig(),
        storage=StorageConfig(db_path=str(tmp_path / "test.db")),
        logging=LoggingConfig(),
    )


@pytest.fixture
def runner(claude_config):
    return ClaudeRunner(claude_config)


class TestClaudeRunner:
    @pytest.mark.asyncio
    async def test_execute_project_not_found(self, runner):
        result = await runner.execute(
            prompt="hello",
            project_path="/nonexistent/path",
            user_id="123",
        )
        assert result.exit_code == -1
        assert "not found" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_cli_not_found(self, runner, claude_config):
        with patch("claudecode_terminal.services.claude.asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("claudecode_terminal.services.claude.save_command", new_callable=AsyncMock):
                result = await runner.execute(
                    prompt="hello",
                    project_path=claude_config.claude.default_project,
                    user_id="123",
                )
        assert result.exit_code == -1
        assert "not found" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_execute_success(self, runner, claude_config):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Hello from Claude!", b""))
        mock_proc.returncode = 0

        with patch("claudecode_terminal.services.claude.asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("claudecode_terminal.services.claude.save_command", new_callable=AsyncMock):
                result = await runner.execute(
                    prompt="hello",
                    project_path=claude_config.claude.default_project,
                    user_id="123",
                )
        assert result.exit_code == 0
        assert result.stdout == "Hello from Claude!"

    @pytest.mark.asyncio
    async def test_execute_timeout(self, runner, claude_config):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=[asyncio.TimeoutError, (b"", b"")])
        mock_proc.kill = MagicMock()

        with patch("claudecode_terminal.services.claude.asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("claudecode_terminal.services.claude.save_command", new_callable=AsyncMock):
                result = await runner.execute(
                    prompt="long task",
                    project_path=claude_config.claude.default_project,
                    user_id="123",
                )
        assert result.exit_code == -1
        assert "timed out" in result.stderr.lower()

    def test_model_alias_resolution(self):
        from claudecode_terminal.config import MODEL_ALIASES

        assert "opus" in MODEL_ALIASES
        assert "sonnet" in MODEL_ALIASES
        assert "haiku" in MODEL_ALIASES
        assert all("claude-" in v for v in MODEL_ALIASES.values())
