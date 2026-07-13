# -*- coding: utf-8 -*-
"""Launching and tracking system Chrome processes (one per profile).

The app does not bundle Chromium — it finds the system-installed Chrome.
Tracking launched PIDs gives us duplicate-launch prevention, the live
running indicator, and per-group / global "close all".
"""

import os
import shutil
import subprocess
import sys

GMAIL_SIGNUP_URL = "https://accounts.google.com/signup"

_WINDOWS_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
_MAC_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_LINUX_CHROME_NAMES = ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]


def find_chrome(configured_path: str = "") -> str:
    """Return the Chrome executable path, or '' if not found."""
    if configured_path and os.path.isfile(configured_path):
        return configured_path
    if sys.platform.startswith("win"):
        for path in _WINDOWS_CHROME_PATHS:
            if os.path.isfile(path):
                return path
        return shutil.which("chrome") or ""
    if sys.platform == "darwin" and os.path.isfile(_MAC_CHROME_PATH):
        return _MAC_CHROME_PATH
    for name in _LINUX_CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return ""


class ChromeLauncher:
    def __init__(self):
        self._procs = {}  # profile_id -> subprocess.Popen

    def is_running(self, profile_id: str) -> bool:
        proc = self._procs.get(profile_id)
        if proc is None:
            return False
        if proc.poll() is not None:
            del self._procs[profile_id]
            return False
        return True

    def running_ids(self) -> set:
        return {pid for pid in list(self._procs) if self.is_running(pid)}

    def launch(self, profile_id: str, chrome_path: str, user_data_dir: str, url: str = "") -> bool:
        """Start Chrome for a profile. Returns False if it is already running."""
        if self.is_running(profile_id):
            return False
        os.makedirs(user_data_dir, exist_ok=True)
        cmd = [chrome_path, f"--user-data-dir={user_data_dir}", "--no-first-run", "--no-default-browser-check"]
        if url:
            cmd.append(url)
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        self._procs[profile_id] = subprocess.Popen(
            cmd, creationflags=creationflags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True

    def close(self, profile_id: str) -> None:
        proc = self._procs.pop(profile_id, None)
        if proc is None or proc.poll() is not None:
            return
        if sys.platform.startswith("win"):
            # terminate the whole Chrome process tree, not just the launcher stub
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            proc.terminate()

    def close_many(self, profile_ids) -> None:
        for pid in list(profile_ids):
            self.close(pid)

    def close_all(self) -> None:
        self.close_many(list(self._procs))
