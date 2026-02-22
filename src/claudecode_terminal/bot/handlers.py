"""Telegram bot command handlers."""

from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from claudecode_terminal.bot.security import user_id_required
from claudecode_terminal.config import MODEL_ALIASES, get_config
from claudecode_terminal.services.claude import ClaudeRunner
from claudecode_terminal.services.shell import ShellRunner
from claudecode_terminal.storage.database import get_recent_commands
from claudecode_terminal.utils.formatting import (
    format_claude_result,
    format_shell_result,
    send_long_message,
)

logger = logging.getLogger(__name__)

# Lazy-initialized service instances
_claude_runner: ClaudeRunner | None = None
_shell_runner: ShellRunner | None = None


def _get_claude_runner() -> ClaudeRunner:
    global _claude_runner
    if _claude_runner is None:
        _claude_runner = ClaudeRunner(get_config())
    return _claude_runner


def _get_shell_runner() -> ShellRunner:
    global _shell_runner
    if _shell_runner is None:
        _shell_runner = ShellRunner(get_config())
    return _shell_runner


def _get_project(context: ContextTypes.DEFAULT_TYPE) -> str:
    config = get_config()
    return context.user_data.get("project", config.claude.default_project)  # type: ignore[union-attr]


# --- Handlers ---


@user_id_required
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    from claudecode_terminal import __version__

    await update.message.reply_text(  # type: ignore[union-attr]
        f"ClaudeCode Terminal v{__version__}\n\n"
        "Control Claude Code remotely via Telegram.\n\n"
        "Type any message to send it to Claude Code,\n"
        "or use /help to see all commands."
    )


@user_id_required
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    project = _get_project(context)
    model = context.user_data.get("model", get_config().claude.default_model)  # type: ignore[union-attr]

    await update.message.reply_text(  # type: ignore[union-attr]
        f"ClaudeCode Terminal\n"
        f"{'=' * 30}\n"
        f"Project: {project}\n"
        f"Model: {model}\n"
        f"{'=' * 30}\n\n"
        "Commands:\n"
        "  /ask <prompt>    - Ask Claude Code\n"
        "  /shell <cmd>     - Run shell command\n"
        "  /project <path>  - Switch project\n"
        "  /model <name>    - Change model\n"
        "  /continue [msg]  - Continue conversation\n"
        "  /system <prompt> - Set system prompt\n"
        "  /maxturns <n>    - Set max turns\n"
        "  /history         - Recent commands\n"
        "  /settings        - Current settings\n"
        "  /help            - This help\n\n"
        "Tip: Type any text to send directly to Claude Code."
    )


@user_id_required
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages - send to Claude Code."""
    text = update.message.text.strip()  # type: ignore[union-attr]
    if not text:
        return

    project = _get_project(context)
    user_id = str(update.effective_user.id)  # type: ignore[union-attr]
    await _execute_claude_and_reply(update, context, text, project, user_id)


@user_id_required
async def ask_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ask <prompt> command."""
    if not context.args:
        await update.message.reply_text("Usage: /ask <prompt>")  # type: ignore[union-attr]
        return

    prompt = " ".join(context.args)
    project = _get_project(context)
    user_id = str(update.effective_user.id)  # type: ignore[union-attr]
    await _execute_claude_and_reply(update, context, prompt, project, user_id)


@user_id_required
async def shell_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /shell <cmd> command."""
    if not context.args:
        await update.message.reply_text("Usage: /shell <command>")  # type: ignore[union-attr]
        return

    command = " ".join(context.args)
    user_id = str(update.effective_user.id)  # type: ignore[union-attr]
    project = _get_project(context)

    result = await _get_shell_runner().execute(command, user_id, cwd=project)
    message = format_shell_result(result, command)
    await send_long_message(update, message)


@user_id_required
async def exec_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /exec <cmd> command (alias for /shell)."""
    await shell_handler.__wrapped__(update, context)  # type: ignore[attr-defined]


@user_id_required
async def project_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /project [path] command."""
    if not context.args:
        project = _get_project(context)
        await update.message.reply_text(f"Current project: {project}")  # type: ignore[union-attr]
        return

    path = " ".join(context.args)
    resolved = Path(path).expanduser().resolve()

    if not resolved.is_dir():
        await update.message.reply_text(f"Directory not found: {resolved}")  # type: ignore[union-attr]
        return

    context.user_data["project"] = str(resolved)  # type: ignore[index]
    await update.message.reply_text(f"Project switched to: {resolved}")  # type: ignore[union-attr]


@user_id_required
async def model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /model [name] command."""
    if not context.args:
        current = context.user_data.get("model", get_config().claude.default_model)  # type: ignore[union-attr]
        available = ", ".join(MODEL_ALIASES.keys())
        await update.message.reply_text(  # type: ignore[union-attr]
            f"Current model: {current}\n"
            f"Available: {available}\n\n"
            "Usage: /model <name>"
        )
        return

    model_name = context.args[0].lower()
    if model_name not in MODEL_ALIASES:
        available = ", ".join(MODEL_ALIASES.keys())
        await update.message.reply_text(f"Unknown model: {model_name}\nAvailable: {available}")  # type: ignore[union-attr]
        return

    context.user_data["model"] = model_name  # type: ignore[index]
    await update.message.reply_text(  # type: ignore[union-attr]
        f"Model changed to: {model_name} ({MODEL_ALIASES[model_name]})"
    )


@user_id_required
async def maxturns_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /maxturns [n] command."""
    if not context.args:
        current = context.user_data.get("max_turns", 0)  # type: ignore[union-attr]
        label = str(current) if current > 0 else "unlimited"
        await update.message.reply_text(  # type: ignore[union-attr]
            f"Max turns: {label}\n\nUsage: /maxturns <n>\nReset: /maxturns 0"
        )
        return

    try:
        turns = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: /maxturns 5")  # type: ignore[union-attr]
        return

    context.user_data["max_turns"] = max(turns, 0)  # type: ignore[index]
    if turns > 0:
        await update.message.reply_text(f"Max turns set to: {turns}")  # type: ignore[union-attr]
    else:
        await update.message.reply_text("Max turns limit removed.")  # type: ignore[union-attr]


@user_id_required
async def system_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /system [prompt|clear] command."""
    raw_text = update.message.text  # type: ignore[union-attr]
    parts = raw_text.split(None, 1)

    if len(parts) < 2:
        current = context.user_data.get("system_prompt", "")  # type: ignore[union-attr]
        if current:
            await update.message.reply_text(  # type: ignore[union-attr]
                f"System prompt:\n{current}\n\nClear: /system clear"
            )
        else:
            await update.message.reply_text(  # type: ignore[union-attr]
                "No system prompt set.\n\nUsage: /system <prompt text>"
            )
        return

    prompt_text = parts[1].strip()
    if prompt_text.lower() == "clear":
        context.user_data["system_prompt"] = ""  # type: ignore[index]
        await update.message.reply_text("System prompt cleared.")  # type: ignore[union-attr]
    else:
        context.user_data["system_prompt"] = prompt_text  # type: ignore[index]
        await update.message.reply_text(f"System prompt set:\n{prompt_text}")  # type: ignore[union-attr]


@user_id_required
async def continue_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /continue [prompt] command."""
    project = _get_project(context)
    user_id = str(update.effective_user.id)  # type: ignore[union-attr]

    raw_text = update.message.text  # type: ignore[union-attr]
    parts = raw_text.split(None, 1)
    prompt = parts[1] if len(parts) > 1 else "continue"

    await _execute_claude_and_reply(update, context, prompt, project, user_id, force_continue=True)


@user_id_required
async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history command."""
    rows = await get_recent_commands(limit=10)

    if not rows:
        await update.message.reply_text("No command history yet.")  # type: ignore[union-attr]
        return

    lines = ["Recent commands:\n"]
    for i, row in enumerate(rows, 1):
        status = "OK" if row["exit_code"] == 0 else f"ERR({row['exit_code']})"
        cmd = row["command"][:50] + ("..." if len(row["command"]) > 50 else "")
        lines.append(f"{i}. [{status}] {cmd} ({row['execution_time_ms']}ms)")

    await update.message.reply_text("\n".join(lines))  # type: ignore[union-attr]


@user_id_required
async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command."""
    config = get_config()
    project = _get_project(context)
    model = context.user_data.get("model", config.claude.default_model)  # type: ignore[union-attr]
    max_turns = context.user_data.get("max_turns", 0)  # type: ignore[union-attr]
    system_prompt = context.user_data.get("system_prompt", "")  # type: ignore[union-attr]

    turns_label = str(max_turns) if max_turns > 0 else "unlimited"
    system_label = system_prompt if system_prompt else "(none)"

    await update.message.reply_text(  # type: ignore[union-attr]
        f"Current Settings\n"
        f"{'=' * 25}\n"
        f"Project: {project}\n"
        f"Model: {model}\n"
        f"Max turns: {turns_label}\n"
        f"System prompt: {system_label}\n"
        f"Claude timeout: {config.claude.timeout}s\n"
        f"Shell timeout: {config.shell.timeout}s\n"
        f"Shell enabled: {config.shell.enabled}"
    )


# --- Internal helpers ---


async def _execute_claude_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prompt: str,
    project: str,
    user_id: str,
    force_continue: bool = False,
) -> None:
    """Execute Claude Code and send the result."""
    thinking_msg = await update.message.reply_text("Claude is thinking...")  # type: ignore[union-attr]

    model = context.user_data.get("model", "")  # type: ignore[union-attr]
    max_turns = context.user_data.get("max_turns", 0)  # type: ignore[union-attr]
    system_prompt = context.user_data.get("system_prompt", "")  # type: ignore[union-attr]

    result = await _get_claude_runner().execute(
        prompt=prompt,
        project_path=project,
        user_id=user_id,
        model=model,
        max_turns=max_turns,
        system_prompt=system_prompt,
        continue_conversation=force_continue,
    )

    # Delete the "thinking" message
    try:
        await thinking_msg.delete()
    except Exception:
        pass

    # Format and send result
    project_name = Path(project).name
    message = format_claude_result(result, project_name)
    await send_long_message(update, message)
