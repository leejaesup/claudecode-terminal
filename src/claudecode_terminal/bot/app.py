"""Telegram bot application setup and lifecycle."""

from __future__ import annotations

import asyncio
import logging
import signal

from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from claudecode_terminal.bot.handlers import (
    ask_handler,
    continue_handler,
    exec_handler,
    help_handler,
    history_handler,
    maxturns_handler,
    model_handler,
    project_handler,
    settings_handler,
    shell_handler,
    start_handler,
    system_handler,
    text_handler,
)
from claudecode_terminal.config import AppConfig
from claudecode_terminal.storage.database import close_db, init_db

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand("ask", "Ask Claude Code a question"),
    BotCommand("shell", "Execute a shell command"),
    BotCommand("project", "Switch or view project directory"),
    BotCommand("model", "Change Claude model (opus/sonnet/haiku)"),
    BotCommand("continue", "Continue previous conversation"),
    BotCommand("system", "Set system prompt"),
    BotCommand("maxturns", "Set max conversation turns"),
    BotCommand("history", "View recent command history"),
    BotCommand("settings", "View current settings"),
    BotCommand("help", "Show help message"),
]


async def run_bot(config: AppConfig) -> None:
    """Start and run the Telegram bot."""
    if not config.bot.token:
        raise ValueError("Bot token not configured. Run 'claudecode-terminal init' first.")

    # Initialize database
    await init_db(config.storage.db_path)

    # Build application
    app = Application.builder().token(config.bot.token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("ask", ask_handler))
    app.add_handler(CommandHandler("shell", shell_handler))
    app.add_handler(CommandHandler("exec", exec_handler))
    app.add_handler(CommandHandler("project", project_handler))
    app.add_handler(CommandHandler("model", model_handler))
    app.add_handler(CommandHandler("maxturns", maxturns_handler))
    app.add_handler(CommandHandler("system", system_handler))
    app.add_handler(CommandHandler("continue", continue_handler))
    app.add_handler(CommandHandler("history", history_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Initialize and start
    await app.initialize()
    await app.bot.set_my_commands(BOT_COMMANDS)
    await app.start()
    assert app.updater is not None
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("Bot started. Waiting for messages...")

    # Wait for shutdown signal
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()

    # Graceful shutdown
    logger.info("Shutting down bot...")
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    await close_db()
    logger.info("Bot stopped.")
