"""Tests for configuration module."""

from __future__ import annotations

from claudecode_terminal.config import (
    MODEL_ALIASES,
    AppConfig,
    BotConfig,
    ClaudeConfig,
    save_config,
    load_config,
    CONFIG_FILE,
)


class TestModelAliases:
    def test_opus(self):
        assert "opus" in MODEL_ALIASES
        assert "claude-opus" in MODEL_ALIASES["opus"]

    def test_sonnet(self):
        assert "sonnet" in MODEL_ALIASES
        assert "claude-sonnet" in MODEL_ALIASES["sonnet"]

    def test_haiku(self):
        assert "haiku" in MODEL_ALIASES
        assert "claude-haiku" in MODEL_ALIASES["haiku"]


class TestAppConfig:
    def test_defaults(self):
        config = AppConfig()
        assert config.bot.token == ""
        assert config.bot.allowed_users == []
        assert config.claude.default_model == "sonnet"
        assert config.claude.timeout == 300
        assert config.shell.timeout == 30
        assert config.shell.enabled is True

    def test_save_and_load(self, tmp_path, monkeypatch):
        import claudecode_terminal.config as cfg_module

        config_file = tmp_path / "config.toml"
        config_dir = tmp_path

        monkeypatch.setattr(cfg_module, "CONFIG_FILE", config_file)
        monkeypatch.setattr(cfg_module, "CONFIG_DIR", config_dir)

        config = AppConfig(
            bot=BotConfig(token="test-token-123", allowed_users=[111, 222]),
            claude=ClaudeConfig(default_project="/tmp/test", default_model="opus", timeout=600),
        )

        save_config(config)
        assert config_file.exists()

        loaded = load_config()
        assert loaded.bot.token == "test-token-123"
        assert loaded.bot.allowed_users == [111, 222]
        assert loaded.claude.default_project == "/tmp/test"
        assert loaded.claude.default_model == "opus"
        assert loaded.claude.timeout == 600
