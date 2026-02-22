"""Tests for CLI module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from claudecode_terminal.cli import app

runner = CliRunner()


class TestCli:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "claudecode-terminal v" in result.output

    def test_status_not_configured(self, tmp_path, monkeypatch):
        import claudecode_terminal.config as cfg_module

        monkeypatch.setattr(cfg_module, "CONFIG_FILE", tmp_path / "nonexistent.toml")
        monkeypatch.setattr(cfg_module, "PID_FILE", tmp_path / "bot.pid")

        # Re-import cli to pick up monkeypatched values
        from claudecode_terminal import cli as cli_module

        monkeypatch.setattr(cli_module, "CONFIG_FILE", tmp_path / "nonexistent.toml")
        monkeypatch.setattr(cli_module, "PID_FILE", tmp_path / "bot.pid")

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "not running" in result.output.lower()

    def test_start_without_config(self, tmp_path, monkeypatch):
        import claudecode_terminal.cli as cli_module

        monkeypatch.setattr(cli_module, "CONFIG_FILE", tmp_path / "nonexistent.toml")

        result = runner.invoke(app, ["start"])
        assert result.exit_code == 1

    def test_stop_when_not_running(self, tmp_path, monkeypatch):
        import claudecode_terminal.cli as cli_module

        monkeypatch.setattr(cli_module, "PID_FILE", tmp_path / "bot.pid")

        result = runner.invoke(app, ["stop"])
        assert result.exit_code == 0
        assert "not running" in result.output.lower()

    def test_config_without_setup(self, tmp_path, monkeypatch):
        import claudecode_terminal.cli as cli_module

        monkeypatch.setattr(cli_module, "CONFIG_FILE", tmp_path / "nonexistent.toml")

        result = runner.invoke(app, ["config"])
        assert result.exit_code == 1

    def test_logs_no_file(self, tmp_path, monkeypatch):
        import claudecode_terminal.cli as cli_module

        monkeypatch.setattr(cli_module, "LOG_FILE", tmp_path / "nonexistent.log")

        result = runner.invoke(app, ["logs"])
        assert result.exit_code == 0
        assert "no log" in result.output.lower()
