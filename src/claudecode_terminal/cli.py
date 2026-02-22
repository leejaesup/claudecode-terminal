"""CLI entry point using typer."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from claudecode_terminal import __version__
from claudecode_terminal.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    LOG_FILE,
    MODEL_ALIASES,
    PID_FILE,
    AppConfig,
    BotConfig,
    ClaudeConfig,
    LoggingConfig,
    ShellConfig,
    StorageConfig,
    ensure_config_dir,
    load_config,
    save_config,
)
from claudecode_terminal.daemon import daemonize, read_pid, stop_daemon, write_pid
from claudecode_terminal.utils.system import check_claude_cli, check_project_dir

app = typer.Typer(
    name="claudecode-terminal",
    help="Control Claude Code remotely via Telegram.",
    add_completion=False,
)
console = Console()


@app.command()
def init() -> None:
    """Interactive setup wizard."""
    console.print(f"\n[bold]ClaudeCode Terminal v{__version__}[/bold]")
    console.print("Interactive Setup\n")

    # 1. Check Claude Code CLI
    console.print("[dim]Checking Claude Code CLI...[/dim]")
    installed, version_info = check_claude_cli()
    if installed:
        console.print(f"  Claude Code: [green]{version_info}[/green]")
    else:
        console.print(f"  [yellow]Warning: {version_info}[/yellow]")
        console.print("  You can still configure the bot, but Claude Code must be installed to use it.\n")

    # 2. Bot Token
    console.print("\n[bold]Step 1:[/bold] Telegram Bot Token")
    console.print("  Create a bot at https://t.me/BotFather and paste the token below.")
    token = typer.prompt("  Bot Token", default="", show_default=False)
    if not token:
        console.print("[red]Bot token is required.[/red]")
        raise typer.Exit(1)

    # 3. Allowed User IDs
    console.print("\n[bold]Step 2:[/bold] Allowed Telegram User IDs")
    console.print("  Send /start to @userinfobot to find your Telegram user ID.")
    console.print("  Enter multiple IDs separated by commas, or leave empty to allow all.")
    user_ids_str = typer.prompt("  User IDs", default="", show_default=False)
    allowed_users: list[int] = []
    if user_ids_str:
        try:
            allowed_users = [int(uid.strip()) for uid in user_ids_str.split(",") if uid.strip()]
        except ValueError:
            console.print("[red]Invalid user ID format. Use numbers only.[/red]")
            raise typer.Exit(1)

    # 4. Default project directory
    console.print("\n[bold]Step 3:[/bold] Default Project Directory")
    default_project = typer.prompt("  Project path", default="~/projects")
    valid, resolved = check_project_dir(default_project)
    if not valid:
        console.print(f"  [yellow]Warning: {resolved}[/yellow]")
        create = typer.confirm("  Create this directory?", default=True)
        if create:
            Path(default_project).expanduser().resolve().mkdir(parents=True, exist_ok=True)
            console.print("  [green]Directory created.[/green]")

    # 5. Default model
    console.print("\n[bold]Step 4:[/bold] Default Claude Model")
    available = ", ".join(MODEL_ALIASES.keys())
    default_model = typer.prompt(f"  Model ({available})", default="sonnet")
    if default_model not in MODEL_ALIASES:
        console.print(f"[yellow]Unknown model '{default_model}', using 'sonnet'.[/yellow]")
        default_model = "sonnet"

    # Save config
    config = AppConfig(
        bot=BotConfig(token=token, allowed_users=allowed_users),
        claude=ClaudeConfig(default_project=default_project, default_model=default_model),
        shell=ShellConfig(),
        storage=StorageConfig(),
        logging=LoggingConfig(),
    )
    save_config(config)

    console.print(f"\n[green]Configuration saved to {CONFIG_FILE}[/green]")
    console.print("\nNext steps:")
    console.print("  [bold]claudecode-terminal start[/bold]         Start the bot")
    console.print("  [bold]claudecode-terminal start --daemon[/bold] Start in background\n")


@app.command()
def start(
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run in background"),
) -> None:
    """Start the Telegram bot."""
    # Check config
    if not CONFIG_FILE.exists():
        console.print("[red]Configuration not found.[/red]")
        console.print("Run [bold]claudecode-terminal init[/bold] first.")
        raise typer.Exit(1)

    config = load_config()
    if not config.bot.token:
        console.print("[red]Bot token not configured.[/red]")
        console.print("Run [bold]claudecode-terminal init[/bold] to set it up.")
        raise typer.Exit(1)

    # Check if already running
    existing_pid = read_pid(PID_FILE)
    if existing_pid is not None:
        console.print(f"[yellow]Bot is already running (PID: {existing_pid}).[/yellow]")
        console.print("Use [bold]claudecode-terminal stop[/bold] to stop it first.")
        raise typer.Exit(1)

    # Check Claude CLI
    installed, version_info = check_claude_cli()
    if not installed:
        console.print(f"[yellow]Warning: {version_info}[/yellow]")
        console.print("Bot will start, but Claude Code commands will fail.\n")

    # Setup logging
    ensure_config_dir()
    logging.basicConfig(
        level=getattr(logging, config.logging.level.upper(), logging.WARNING),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(Path(config.logging.file).expanduser().resolve())),
            *([] if daemon else [logging.StreamHandler()]),
        ],
    )

    if daemon:
        console.print(f"Starting bot in background...")
        log_path = Path(config.logging.file).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        daemonize(log_path)

    write_pid(PID_FILE)

    if not daemon:
        console.print(f"[green]Bot started![/green] Send /help to your bot on Telegram.")
        console.print("Press Ctrl+C to stop.\n")

    try:
        from claudecode_terminal.bot.app import run_bot

        asyncio.run(run_bot(config))
    except KeyboardInterrupt:
        pass
    finally:
        PID_FILE.unlink(missing_ok=True)
        if not daemon:
            console.print("\n[dim]Bot stopped.[/dim]")


@app.command()
def stop() -> None:
    """Stop the running bot."""
    if stop_daemon(PID_FILE):
        console.print("[green]Bot stopped.[/green]")
    else:
        console.print("[yellow]Bot is not running.[/yellow]")


@app.command()
def status() -> None:
    """Check bot running status."""
    pid = read_pid(PID_FILE)
    if pid is not None:
        console.print(f"[green]Bot is running[/green] (PID: {pid})")
    else:
        console.print("[dim]Bot is not running.[/dim]")

    if CONFIG_FILE.exists():
        config = load_config()
        console.print(f"\nConfig: {CONFIG_FILE}")
        console.print(f"Project: {config.claude.default_project}")
        console.print(f"Model: {config.claude.default_model}")
        console.print(f"Users: {config.bot.allowed_users or 'all'}")
    else:
        console.print("\n[yellow]Not configured. Run 'claudecode-terminal init'.[/yellow]")


@app.command()
def config(
    key: str = typer.Argument(None, help="Config key (e.g., claude.timeout)"),
    value: str = typer.Argument(None, help="New value"),
) -> None:
    """View or modify configuration."""
    if not CONFIG_FILE.exists():
        console.print("[red]Not configured. Run 'claudecode-terminal init'.[/red]")
        raise typer.Exit(1)

    cfg = load_config()

    if key is None:
        # Show all config
        table = Table(title="Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("bot.token", cfg.bot.token[:8] + "..." if cfg.bot.token else "(not set)")
        table.add_row("bot.allowed_users", str(cfg.bot.allowed_users) if cfg.bot.allowed_users else "all")
        table.add_row("claude.default_project", cfg.claude.default_project)
        table.add_row("claude.default_model", cfg.claude.default_model)
        table.add_row("claude.timeout", str(cfg.claude.timeout))
        table.add_row("claude.max_output", str(cfg.claude.max_output))
        table.add_row("shell.timeout", str(cfg.shell.timeout))
        table.add_row("shell.enabled", str(cfg.shell.enabled))
        table.add_row("storage.db_path", cfg.storage.db_path)
        table.add_row("logging.level", cfg.logging.level)

        console.print(table)
        return

    if value is None:
        console.print("[red]Usage: claudecode-terminal config <key> <value>[/red]")
        raise typer.Exit(1)

    # Set config value
    parts = key.split(".")
    if len(parts) != 2:
        console.print("[red]Key format: section.key (e.g., claude.timeout)[/red]")
        raise typer.Exit(1)

    section, attr = parts
    section_map = {"bot": cfg.bot, "claude": cfg.claude, "shell": cfg.shell, "storage": cfg.storage, "logging": cfg.logging}

    if section not in section_map:
        console.print(f"[red]Unknown section: {section}[/red]")
        raise typer.Exit(1)

    obj = section_map[section]
    if not hasattr(obj, attr):
        console.print(f"[red]Unknown key: {key}[/red]")
        raise typer.Exit(1)

    # Type coercion
    current = getattr(obj, attr)
    try:
        if isinstance(current, bool):
            typed_value = value.lower() in ("true", "1", "yes")
        elif isinstance(current, int):
            typed_value = int(value)
        elif isinstance(current, list):
            typed_value = [int(v.strip()) for v in value.split(",") if v.strip()]
        else:
            typed_value = value
    except ValueError:
        console.print(f"[red]Invalid value type for {key}[/red]")
        raise typer.Exit(1)

    setattr(obj, attr, typed_value)
    save_config(cfg)
    console.print(f"[green]{key} = {typed_value}[/green]")


@app.command()
def logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """View bot logs."""
    log_path = Path(LOG_FILE).expanduser().resolve()
    if not log_path.exists():
        console.print("[dim]No log file found.[/dim]")
        return

    if follow:
        import subprocess

        try:
            subprocess.run(["tail", "-f", "-n", str(lines), str(log_path)])
        except KeyboardInterrupt:
            pass
    else:
        content = log_path.read_text()
        log_lines = content.strip().split("\n")
        for line in log_lines[-lines:]:
            console.print(line)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"claudecode-terminal v{__version__}")

    installed, version_info = check_claude_cli()
    if installed:
        console.print(f"Claude Code CLI: {version_info}")
    else:
        console.print(f"Claude Code CLI: [yellow]not installed[/yellow]")

    console.print(f"Python: {sys.version.split()[0]}")
    console.print(f"Config: {CONFIG_FILE}")


if __name__ == "__main__":
    app()
