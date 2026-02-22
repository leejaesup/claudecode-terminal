"""Tests for bot security module."""

from __future__ import annotations

from claudecode_terminal.bot.security import BlacklistChecker


class TestBlacklist:
    def setup_method(self):
        self.checker = BlacklistChecker()

    def test_fork_bomb_blocked(self):
        blocked, reason = self.checker.check(":(){ :|:& };:")
        assert blocked
        assert "Fork bomb" in reason

    def test_rm_rf_root_blocked(self):
        blocked, reason = self.checker.check("rm -rf /")
        assert blocked

    def test_mkfs_blocked(self):
        blocked, reason = self.checker.check("mkfs.ext4 /dev/sda1")
        assert blocked

    def test_dd_blocked(self):
        blocked, reason = self.checker.check("dd if=/dev/zero of=/dev/sda")
        assert blocked

    def test_shutdown_blocked(self):
        blocked, reason = self.checker.check("shutdown -h now")
        assert blocked

    def test_interactive_vim_blocked(self):
        blocked, reason = self.checker.check("vim file.txt")
        assert blocked

    def test_interactive_ssh_blocked(self):
        blocked, reason = self.checker.check("ssh user@host")
        assert blocked

    def test_safe_command_allowed(self):
        blocked, _ = self.checker.check("ls -la")
        assert not blocked

    def test_safe_git_allowed(self):
        blocked, _ = self.checker.check("git status")
        assert not blocked

    def test_safe_cat_allowed(self):
        blocked, _ = self.checker.check("cat README.md")
        assert not blocked

    def test_safe_echo_allowed(self):
        blocked, _ = self.checker.check("echo hello world")
        assert not blocked
