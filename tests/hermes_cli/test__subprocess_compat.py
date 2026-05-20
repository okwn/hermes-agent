"""Tests for hermes_cli._subprocess_compat — Windows subprocess compatibility helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import patch

import pytest

from hermes_cli._subprocess_compat import (
    IS_WINDOWS,
    resolve_node_command,
    windows_detach_flags,
    windows_hide_flags,
    windows_detach_popen_kwargs,
)


class TestIsWindows:
    def test_is_windows_is_bool(self):
        assert isinstance(IS_WINDOWS, bool)

    def test_is_windows_matches_platform(self):
        assert IS_WINDOWS == (sys.platform == "win32")


class TestResolveNodeCommand:
    def test_returns_list(self):
        result = resolve_node_command("python", ["--version"])
        assert isinstance(result, list)
        assert len(result) == 2

    def test_first_arg_is_resolved_path(self):
        result = resolve_node_command("python", ["--version"])
        # resolved path should exist and be executable
        assert os.path.isfile(result[0])

    def test_remaining_args_preserved(self):
        argv = ["--version", "--help"]
        result = resolve_node_command("python", argv)
        assert result[1:] == argv

    def test_nonexistent_command_returns_bare_name(self):
        result = resolve_node_command("definitely-not-a-real-command-xyz", ["--version"])
        assert result[0] == "definitely-not-a-real-command-xyz"
        assert result[1:] == ["--version"]

    def test_resolve_node_command_is_deterministic(self):
        # Calling multiple times with the same args returns the same resolved path
        results = [resolve_node_command("python", ["--version"]) for _ in range(3)]
        assert all(r == results[0] for r in results)


class TestWindowsDetachFlags:
    def test_returns_int(self):
        result = windows_detach_flags()
        assert isinstance(result, int)

    def test_zero_on_non_windows(self):
        if not IS_WINDOWS:
            assert windows_detach_flags() == 0

    def test_nonzero_on_windows_only(self):
        if IS_WINDOWS:
            assert windows_detach_flags() != 0

    def test_contains_no_window_bit(self):
        CREATE_NO_WINDOW = 0x08000000
        if IS_WINDOWS:
            assert windows_detach_flags() & CREATE_NO_WINDOW


class TestWindowsHideFlags:
    def test_returns_int(self):
        result = windows_hide_flags()
        assert isinstance(result, int)

    def test_zero_on_non_windows(self):
        if not IS_WINDOWS:
            assert windows_hide_flags() == 0

    def test_nonzero_on_windows_only(self):
        if IS_WINDOWS:
            assert windows_hide_flags() != 0

    def test_smaller_than_detach_flags(self):
        # hide_flags is a subset of detach_flags (no DETACHED_PROCESS)
        if IS_WINDOWS:
            assert windows_hide_flags() < windows_detach_flags()


class TestWindowsDetachPopenKwargs:
    def test_returns_dict(self):
        result = windows_detach_popen_kwargs()
        assert isinstance(result, dict)

    def test_has_creationflags_on_windows(self):
        if IS_WINDOWS:
            assert "creationflags" in result
            assert isinstance(result["creationflags"], int)
            assert result["creationflags"] != 0

    def test_has_start_new_session_on_posix(self):
        if not IS_WINDOWS:
            result = windows_detach_popen_kwargs()
            assert "start_new_session" in result
            assert result["start_new_session"] is True

    def test_no_conflicting_keys(self):
        result = windows_detach_popen_kwargs()
        # Should not have both keys (one or the other)
        keys = set(result.keys())
        assert keys.issubset({"creationflags", "start_new_session"})
        assert len(keys) == 1


class TestSubprocessCompatIntegration:
    """Verify the helpers actually work with subprocess calls on the current platform."""

    def test_popen_with_detach_kwargs_succeeds(self):
        """Basic smoke test: Popen accepts the kwargs without error."""
        kwargs = windows_detach_popen_kwargs()
        proc = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.exit(0)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
        proc.wait()
        assert proc.returncode == 0

    def test_resolve_node_command_with_python_succeeds(self):
        """Smoke test: resolved python argv works with subprocess."""
        argv = resolve_node_command(sys.executable, ["-c", "print('ok')"])
        result = subprocess.run(argv, capture_output=True, text=True)
        assert result.returncode == 0
        assert result.stdout.strip() == "ok"