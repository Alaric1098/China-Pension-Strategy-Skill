"""Pytest compatibility bootstrap for restricted Windows environments.

Some restricted Windows process environments map pytest's explicit POSIX
directory modes to restrictive DACLs. Two test-only problems are handled here:

1. Directory-mode poisoning (root cause of every tmp_path failure).
   pytest's tmpdir plugin creates its basetemp root and numbered child dirs
   with `mode=0o700`. On this Windows host a directory created with an
   explicit POSIX mode gets a restrictive DACL and becomes UNSCANNABLE —
   `os.scandir` raises PermissionError (WinError 5) — which breaks pytest's
   basetemp numbering sweep and session-finish cleanup. Fix: strip the mode
   argument from directory creation on Windows so dirs get the default DACL.

2. Stale unreadable temproot. If an earlier run created an unreadable pytest
   root in the system temporary directory, redirect `PYTEST_DEBUG_TEMPROOT`
   to a workspace-local ignored directory.

The mode patch applies process-wide for the whole pytest run (including
code under test), which is safe because no Windows test asserts POSIX mode
bits. Both fixes are no-ops on non-Windows platforms and do not affect the
installed library or CLI.
"""

import getpass
import os
import tempfile
from pathlib import Path


def _default_temproot_unusable() -> bool:
    """True when the default %TEMP% pytest temproot is not scannable."""
    root = Path(tempfile.gettempdir())
    username = getpass.getuser() or "unknown"
    for candidate in (root / f"pytest-of-{username}", root / "pytest-of-unknown"):
        if candidate.exists():
            try:
                next(candidate.iterdir())
            except (PermissionError, OSError):
                return True
    return False


def _install_windows_dir_mode_fix() -> None:
    if os.name != "nt":
        return

    _orig_mkdir = os.mkdir

    def _safe_mkdir(path, mode=0o777, *, dir_fd=None):
        if dir_fd is not None:
            return _orig_mkdir(path, dir_fd=dir_fd)
        return _orig_mkdir(path)

    _orig_makedirs = os.makedirs

    def _safe_makedirs(name, mode=0o777, exist_ok=False):
        return _orig_makedirs(name, exist_ok=exist_ok)

    os.mkdir = _safe_mkdir
    os.makedirs = _safe_makedirs


def _redirect_stale_temproot() -> None:
    """Point pytest's default temproot at the workspace when %TEMP% is poisoned."""
    if os.environ.get("PYTEST_DEBUG_TEMPROOT"):
        return
    if os.name == "nt" and _default_temproot_unusable():
        workspace_root = Path.cwd()
        fallback = workspace_root / ".pytest-temproot"
        fallback.mkdir(exist_ok=True)
        os.environ["PYTEST_DEBUG_TEMPROOT"] = str(fallback)


def pytest_configure(config):
    """Apply the Windows dir-mode fix and stale-temproot redirect."""
    _install_windows_dir_mode_fix()
    _redirect_stale_temproot()
