"""Process daemonization and PID file management."""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def write_pid(pid_file: Path) -> None:
    """Write the current process PID to file."""
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))


def read_pid(pid_file: Path) -> int | None:
    """Read PID from file and verify the process exists."""
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # Check if process exists
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        pid_file.unlink(missing_ok=True)
        return None


def stop_daemon(pid_file: Path) -> bool:
    """Stop a running daemon by PID file."""
    pid = read_pid(pid_file)
    if pid is None:
        return False

    # Send SIGTERM
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        return True

    # Wait up to 5 seconds
    for _ in range(50):
        try:
            os.kill(pid, 0)
            time.sleep(0.1)
        except ProcessLookupError:
            pid_file.unlink(missing_ok=True)
            return True

    # Force kill
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    pid_file.unlink(missing_ok=True)
    return True


def daemonize(log_file: Path) -> None:
    """Unix double-fork daemonize."""
    # First fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    os.setsid()

    # Second fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    devnull = open(os.devnull, "r")
    log_fd = open(log_file, "a")

    os.dup2(devnull.fileno(), sys.stdin.fileno())
    os.dup2(log_fd.fileno(), sys.stdout.fileno())
    os.dup2(log_fd.fileno(), sys.stderr.fileno())
