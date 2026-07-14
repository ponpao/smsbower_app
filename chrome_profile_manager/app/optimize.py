# -*- coding: utf-8 -*-
"""Profile optimizer: clears Chrome cache folders to free disk space.

Only disposable cache directories are touched — logins (Cookies), bookmarks,
history and extensions are never deleted. Supports a dry run that reports
how much space would be freed without deleting anything.
"""

import os
import shutil

# Relative to a profile's content dir (e.g. <user-data-dir>/Default)
PROFILE_CACHE_DIRS = [
    "Cache",
    "Code Cache",
    "GPUCache",
    "Media Cache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    os.path.join("Service Worker", "CacheStorage"),
    os.path.join("Service Worker", "ScriptCache"),
]

# Relative to the user-data-dir root (shared between profiles)
ROOT_CACHE_DIRS = [
    "GrShaderCache",
    "ShaderCache",
    "GraphiteDawnCache",
]


def dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _clean_dirs(base: str, rel_dirs: list, dry_run: bool) -> int:
    freed = 0
    for rel in rel_dirs:
        path = os.path.join(base, rel)
        if not os.path.isdir(path):
            continue
        freed += dir_size(path)
        if not dry_run:
            shutil.rmtree(path, ignore_errors=True)
    return freed


def optimize_profile(content_dir: str, dry_run: bool = False) -> int:
    """Clear cache folders for one profile. Returns bytes freed (or freeable)."""
    if not os.path.isdir(content_dir):
        return 0
    return _clean_dirs(content_dir, PROFILE_CACHE_DIRS, dry_run)


def optimize_user_data_root(user_data_dir: str, dry_run: bool = False) -> int:
    """Clear shared cache folders at the user-data-dir root."""
    if not os.path.isdir(user_data_dir):
        return 0
    return _clean_dirs(user_data_dir, ROOT_CACHE_DIRS, dry_run)
