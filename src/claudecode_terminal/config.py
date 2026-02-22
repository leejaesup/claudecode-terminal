"""Configuration management using TOML + environment variables."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

CONFIG_DIR = Path.home() / ".claudecode-terminal"
CONFIG_FILE = CONFIG_DIR / "config.toml"
PID_FILE = CONFIG_DIR / "bot.pid"
LOG_FILE = CONFIG_DIR / "bot.log"

MODEL_ALIASES: dict[str, str] = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}


@dataclass
class BotConfig:
    token: str = ""
    allowed_users: list[int] = field(default_factory=list)


@dataclass
class ClaudeConfig:
    default_project: str = "~/projects"
    default_model: str = "sonnet"
    timeout: int = 300
    max_output: int = 4096


@dataclass
class ShellConfig:
    timeout: int = 30
    enabled: bool = True


@dataclass
class StorageConfig:
    db_path: str = "~/.claudecode-terminal/history.db"


@dataclass
class LoggingConfig:
    level: str = "WARNING"
    file: str = "~/.claudecode-terminal/bot.log"


@dataclass
class AppConfig:
    bot: BotConfig = field(default_factory=BotConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    shell: ShellConfig = field(default_factory=ShellConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def ensure_config_dir() -> None:
    """Create config directory with secure permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)


def load_config() -> AppConfig:
    """Load configuration from TOML file with env var overrides."""
    config = AppConfig()

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)

        bot = data.get("bot", {})
        config.bot.token = bot.get("token", "")
        config.bot.allowed_users = bot.get("allowed_users", [])

        claude = data.get("claude", {})
        config.claude.default_project = claude.get("default_project", config.claude.default_project)
        config.claude.default_model = claude.get("default_model", config.claude.default_model)
        config.claude.timeout = claude.get("timeout", config.claude.timeout)
        config.claude.max_output = claude.get("max_output", config.claude.max_output)

        shell = data.get("shell", {})
        config.shell.timeout = shell.get("timeout", config.shell.timeout)
        config.shell.enabled = shell.get("enabled", config.shell.enabled)

        storage = data.get("storage", {})
        config.storage.db_path = storage.get("db_path", config.storage.db_path)

        logging_cfg = data.get("logging", {})
        config.logging.level = logging_cfg.get("level", config.logging.level)
        config.logging.file = logging_cfg.get("file", config.logging.file)

    # Environment variable overrides
    if env_token := os.environ.get("CLAUDECODE_BOT_TOKEN"):
        config.bot.token = env_token
    if env_users := os.environ.get("CLAUDECODE_ALLOWED_USERS"):
        config.bot.allowed_users = [int(u.strip()) for u in env_users.split(",") if u.strip()]
    if env_project := os.environ.get("CLAUDECODE_DEFAULT_PROJECT"):
        config.claude.default_project = env_project
    if env_model := os.environ.get("CLAUDECODE_DEFAULT_MODEL"):
        config.claude.default_model = env_model
    if env_timeout := os.environ.get("CLAUDECODE_TIMEOUT"):
        config.claude.timeout = int(env_timeout)
    if env_shell_timeout := os.environ.get("CLAUDECODE_SHELL_TIMEOUT"):
        config.shell.timeout = int(env_shell_timeout)
    if env_max_output := os.environ.get("CLAUDECODE_MAX_OUTPUT"):
        config.claude.max_output = int(env_max_output)
    if env_db := os.environ.get("CLAUDECODE_DB_PATH"):
        config.storage.db_path = env_db
    if env_log_level := os.environ.get("CLAUDECODE_LOG_LEVEL"):
        config.logging.level = env_log_level

    return config


def save_config(config: AppConfig) -> None:
    """Save configuration to TOML file."""
    ensure_config_dir()

    data = {
        "bot": {
            "token": config.bot.token,
            "allowed_users": config.bot.allowed_users,
        },
        "claude": {
            "default_project": config.claude.default_project,
            "default_model": config.claude.default_model,
            "timeout": config.claude.timeout,
            "max_output": config.claude.max_output,
        },
        "shell": {
            "timeout": config.shell.timeout,
            "enabled": config.shell.enabled,
        },
        "storage": {
            "db_path": config.storage.db_path,
        },
        "logging": {
            "level": config.logging.level,
            "file": config.logging.file,
        },
    }

    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(data, f)

    os.chmod(CONFIG_FILE, 0o600)


# Global singleton
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get or load the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the global config (for testing)."""
    global _config
    _config = None
