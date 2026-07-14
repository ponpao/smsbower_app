# -*- coding: utf-8 -*-
"""Launching and tracking system Chrome processes (one per profile).

The app does not bundle Chromium — it finds the system-installed Chrome.
Profiles come in two flavors:
  * isolated  — the app's own --user-data-dir folder under data/chrome_profiles
  * system    — an existing profile inside the real Chrome "User Data" folder
                (imported via Scan & Import), launched with
                --user-data-dir=<User Data> --profile-directory=<Profile N>

Tracking launched PIDs gives us duplicate-launch prevention, the live
running indicator, and per-group / global "close all".
"""

import json
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


def default_user_data_path() -> str:
    """The system Chrome 'User Data' directory for the current OS."""
    if sys.platform.startswith("win"):
        return os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    return os.path.expanduser("~/.config/google-chrome")


def scan_system_profiles(base_path: str) -> list:
    """List existing Chrome profiles inside a 'User Data' folder.

    Returns [{"dir": "Profile 1", "name": "Person 1", "gmail": "x@gmail.com"}].
    Reads Local State's profile.info_cache first (has display name + account),
    falling back to each profile folder's Preferences file.
    """
    results = []
    if not os.path.isdir(base_path):
        return results
    info_cache = {}
    local_state = os.path.join(base_path, "Local State")
    if os.path.isfile(local_state):
        try:
            with open(local_state, "r", encoding="utf-8") as f:
                info_cache = json.load(f).get("profile", {}).get("info_cache", {}) or {}
        except (json.JSONDecodeError, OSError):
            info_cache = {}

    def looks_like_profile(name: str) -> bool:
        return name == "Default" or name.startswith("Profile ")

    dirs = sorted(d for d in os.listdir(base_path)
                  if looks_like_profile(d) and os.path.isdir(os.path.join(base_path, d)))
    for d in dirs:
        info = info_cache.get(d, {})
        name = info.get("name") or info.get("gaia_name") or d
        gmail = info.get("user_name", "")
        if not gmail or not info:
            prefs_path = os.path.join(base_path, d, "Preferences")
            if os.path.isfile(prefs_path):
                try:
                    with open(prefs_path, "r", encoding="utf-8") as f:
                        prefs = json.load(f)
                    name = prefs.get("profile", {}).get("name") or name
                    accounts = prefs.get("account_info") or []
                    if accounts and not gmail:
                        gmail = accounts[0].get("email", "")
                except (json.JSONDecodeError, OSError):
                    pass
        results.append({"dir": d, "name": name, "gmail": gmail})
    return results


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

    def launch(self, profile_id: str, chrome_path: str, user_data_dir: str = "",
               url: str = "", profile_directory: str = "") -> bool:
        """Start Chrome for a profile. Returns False if it is already running."""
        if self.is_running(profile_id):
            return False
        cmd = [chrome_path]
        if user_data_dir:
            if not profile_directory:  # only create folders the app owns
                os.makedirs(user_data_dir, exist_ok=True)
            cmd.append(f"--user-data-dir={user_data_dir}")
        if profile_directory:
            cmd.append(f"--profile-directory={profile_directory}")
        else:
            cmd += ["--no-first-run", "--no-default-browser-check"]
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
