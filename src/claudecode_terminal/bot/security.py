"""Authentication for Telegram bot."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Coroutine

from telegram import Update
from telegram.ext import ContextTypes

from claudecode_terminal.config import get_config

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
from claudecode_terminal.services.blacklist import BlacklistChecker, blacklist_checker  # noqa: E402, F401


def is_allowed_user(user_id: int) -> bool:
    """Check if the user ID is in the whitelist."""
    config = get_config()
    allowed = config.bot.allowed_users
    if not allowed:
        return True  # Empty list = allow all (personal use)
    return user_id in allowed


def user_id_required(
    func: Callable[..., Coroutine[Any, Any, None]],
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Decorator to enforce user ID authentication."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if user is None:
            return
        if not is_allowed_user(user.id):
            logger.warning("Unauthorized access: user_id=%d username=%s", user.id, user.username)
            return  # Silent drop
        return await func(update, context)

    return wrapper
