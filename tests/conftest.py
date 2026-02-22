"""Shared test fixtures."""

from __future__ import annotations

import pytest

from claudecode_terminal.config import AppConfig, BotConfig, ClaudeConfig, ShellConfig, StorageConfig, LoggingConfig


@pytest.fixture
def app_config(tmp_path):
    """Create a test configuration."""
    return AppConfig(
        bot=BotConfig(token="test-token", allowed_users=[12345]),
        claude=ClaudeConfig(
            default_project=str(tmp_path / "projects"),
            default_model="sonnet",
            timeout=10,
            max_output=4096,
        ),
        shell=ShellConfig(timeout=5, enabled=True),
        storage=StorageConfig(db_path=str(tmp_path / "test.db")),
        logging=LoggingConfig(level="DEBUG", file=str(tmp_path / "test.log")),
    )
