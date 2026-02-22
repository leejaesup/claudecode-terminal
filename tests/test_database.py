"""Tests for database module."""

from __future__ import annotations

import pytest

from claudecode_terminal.storage.database import close_db, get_recent_commands, init_db, save_command


class TestDatabase:
    @pytest.mark.asyncio
    async def test_init_and_save(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)

        await save_command(
            user_id="123",
            command="echo hello",
            stdout="hello",
            stderr="",
            exit_code=0,
            execution_time_ms=50,
            source="telegram",
        )

        commands = await get_recent_commands(limit=5)
        assert len(commands) == 1
        assert commands[0]["command"] == "echo hello"
        assert commands[0]["exit_code"] == 0

        await close_db()

    @pytest.mark.asyncio
    async def test_multiple_commands_ordering(self, tmp_path):
        db_path = str(tmp_path / "test2.db")
        await init_db(db_path)

        for i in range(5):
            await save_command(
                user_id="123",
                command=f"cmd_{i}",
                stdout=f"out_{i}",
                stderr="",
                exit_code=0,
                execution_time_ms=i * 10,
                source="telegram",
            )

        commands = await get_recent_commands(limit=3)
        assert len(commands) == 3
        # Most recent first
        assert commands[0]["command"] == "cmd_4"
        assert commands[2]["command"] == "cmd_2"

        await close_db()

    @pytest.mark.asyncio
    async def test_source_check_constraint(self, tmp_path):
        db_path = str(tmp_path / "test3.db")
        await init_db(db_path)

        # Valid source: "claude"
        await save_command(
            user_id="123",
            command="test",
            stdout="ok",
            stderr="",
            exit_code=0,
            execution_time_ms=10,
            source="claude",
        )

        commands = await get_recent_commands(limit=1)
        assert commands[0]["source"] == "claude"

        await close_db()
