"""Optional "shut the PC down when the batch finishes" support.

The shutdown is always preceded by a cancelable warning dialog in the UI; this
module only performs the platform call once that countdown expires.
"""

from __future__ import annotations

import os
import subprocess
import sys

SHUTDOWN_GRACE_SECONDS = 60


def shutdown_command() -> list[str]:
    """Platform-specific command that powers the machine off."""
    if sys.platform.startswith("win"):
        return ["shutdown", "/s", "/t", "0"]
    if sys.platform == "darwin":
        return ["osascript", "-e", 'tell application "System Events" to shut down']
    # Linux/BSD: systemd first, plain shutdown as a fallback (handled by caller).
    return ["systemctl", "poweroff"]


def fallback_shutdown_command() -> list[str] | None:
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return None
    return ["shutdown", "-h", "now"]


def shutdown_pc(dry_run: bool = False) -> tuple[bool, str]:
    """Power off the machine. Returns ``(ok, message)`` — never raises.

    ``dry_run`` is used by the test suite and by the "simulate" option so the
    whole code path can be exercised without actually killing the session.
    """
    command = shutdown_command()
    if dry_run or os.environ.get("TKDL_NO_SHUTDOWN"):
        return True, "Shutdown simulated (dry run): " + " ".join(command)
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, "Shutdown command issued."
    except (OSError, subprocess.SubprocessError) as exc:
        fallback = fallback_shutdown_command()
        if fallback:
            try:
                subprocess.Popen(fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True, "Shutdown command issued."
            except (OSError, subprocess.SubprocessError) as exc2:
                return False, f"Shutdown failed: {exc2}"
        return False, f"Shutdown failed: {exc}"


def _open_native(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def open_folder(path: str) -> None:
    """Reveal a folder in the OS file manager (used by the 'Open folder' button)."""
    try:
        _open_native(path)
    except (OSError, subprocess.SubprocessError, AttributeError):
        pass


def play_file(path: str) -> bool:
    """Launch a downloaded video with the OS's default player.

    Used by each queue row's "Play" button — distinct from ``open_folder``,
    which only reveals the containing directory. Returns ``False`` (without
    raising) if the file no longer exists or nothing is registered to open it.
    """
    if not path or not os.path.isfile(path):
        return False
    try:
        _open_native(path)
        return True
    except (OSError, subprocess.SubprocessError, AttributeError):
        return False
