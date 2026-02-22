"""SQLite database management for command history."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None


async def init_db(db_path: str) -> None:
    """Initialize database and create tables."""
    global _db
    resolved = Path(db_path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)

    _db = await aiosqlite.connect(str(resolved))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode = WAL")

    await _db.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            command TEXT NOT NULL,
            stdout TEXT DEFAULT '',
            stderr TEXT DEFAULT '',
            exit_code INTEGER,
            execution_time_ms INTEGER,
            source TEXT DEFAULT 'telegram'
                CHECK(source IN ('telegram', 'claude')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_commands_created_at ON commands(created_at)")
    await _db.commit()
    logger.info("Database initialized: %s", resolved)


async def get_db() -> aiosqlite.Connection:
    """Get the database connection."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("Database closed")


async def save_command(
    user_id: str,
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    execution_time_ms: int,
    source: str = "telegram",
) -> None:
    """Save a command execution to history."""
    try:
        db = await get_db()
        await db.execute(
            """INSERT INTO commands (user_id, command, stdout, stderr, exit_code, execution_time_ms, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, command, stdout, stderr, exit_code, execution_time_ms, source),
        )
        await db.commit()
    except Exception:
        logger.exception("Failed to save command history")


async def get_recent_commands(limit: int = 10) -> list[dict]:
    """Get recent command history."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT command, exit_code, execution_time_ms, source, created_at FROM commands ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
