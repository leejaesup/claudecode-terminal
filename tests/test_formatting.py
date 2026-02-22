"""Tests for message formatting utilities."""

from __future__ import annotations

from claudecode_terminal.storage.models import ExecutionResult
from claudecode_terminal.utils.formatting import (
    format_claude_result,
    format_duration,
    format_shell_result,
    split_message,
)


class TestSplitMessage:
    def test_short_message(self):
        result = split_message("hello", max_len=100)
        assert result == ["hello"]

    def test_exact_length(self):
        text = "a" * 100
        result = split_message(text, max_len=100)
        assert result == [text]

    def test_split_at_newline(self):
        text = "line1\nline2\nline3"
        result = split_message(text, max_len=10)
        assert len(result) >= 2
        assert "line1" in result[0]

    def test_split_no_newline(self):
        text = "a" * 200
        result = split_message(text, max_len=100)
        assert len(result) == 2
        assert len(result[0]) == 100
        assert len(result[1]) == 100

    def test_empty_string(self):
        result = split_message("")
        assert result == []


class TestFormatDuration:
    def test_milliseconds(self):
        assert format_duration(500) == "500ms"

    def test_seconds(self):
        assert format_duration(2500) == "2.5s"

    def test_minutes(self):
        assert format_duration(125000) == "2m 5s"

    def test_zero(self):
        assert format_duration(0) == "0ms"


class TestFormatResults:
    def test_claude_result(self):
        result = ExecutionResult(stdout="Hello!", execution_time_ms=1500)
        output = format_claude_result(result, "my-project")
        assert "Claude" in output
        assert "my-project" in output
        assert "Hello!" in output
        assert "1.5s" in output

    def test_claude_result_no_output(self):
        result = ExecutionResult(execution_time_ms=100)
        output = format_claude_result(result, "proj")
        assert "(no output)" in output

    def test_shell_result_success(self):
        result = ExecutionResult(stdout="output", exit_code=0)
        output = format_shell_result(result, "ls -la")
        assert "$ ls -la" in output
        assert "[OK]" in output

    def test_shell_result_error(self):
        result = ExecutionResult(stderr="not found", exit_code=1)
        output = format_shell_result(result, "bad_cmd")
        assert "[ERR(1)]" in output

    def test_shell_result_blocked(self):
        result = ExecutionResult(blocked=True, reason="Fork bomb")
        output = format_shell_result(result, ":(){ :|:& };:")
        assert "Blocked" in output
        assert "Fork bomb" in output
