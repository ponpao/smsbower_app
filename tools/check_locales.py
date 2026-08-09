#!/usr/bin/env python3
"""Verify that en.json and kh.json cover every translation key used in the code.

Run it after touching the UI::

    python tools/check_locales.py

Exits non-zero and prints the offending keys when something is missing, so it can
be wired into CI or a pre-commit hook.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "tk_downloader"
LOCALES = SOURCE_DIR / "locales"

# Keys built at runtime from an enum value rather than written as a literal.
DYNAMIC_KEYS = {
    *(f"status.{name}" for name in (
        "queued", "extracting", "downloading", "processing",
        "completed", "skipped", "error", "paused", "cancelled",
    )),
    *(f"quality.{name}" for name in ("best", "1080p", "720p", "480p", "360p", "audio")),
    *(f"perf.mode_{name}" for name in ("cpu", "gpu", "both", "none")),
    *(f"stats.{name}" for name in ("total", "done", "active", "failed")),
    "theme.to_dark", "theme.to_light",
    "table.num", "table.profile", "table.title", "table.video_id", "table.status",
    "table.progress", "table.speed", "table.eta", "table.actions",
}

# Values that legitimately read the same in every language (resolution labels).
IDENTICAL_OK = {"quality.1080p", "quality.720p", "quality.480p", "quality.360p"}

LITERAL_PATTERNS = (
    re.compile(r'\.bind\([^,]+,\s*"[a-z_]+"\s*,\s*"([a-z_]+\.[a-z_0-9]+)"'),
    re.compile(r'\bt\(\s*"([a-z_]+\.[a-z_0-9]+)"'),
    re.compile(r'_key\s*=\s*"([a-z_]+\.[a-z_0-9]+)"'),
    re.compile(r'(?:title_key|body_key)\s*=\s*"([a-z_]+\.[a-z_0-9]+)"'),
)


def collect_used_keys() -> set[str]:
    keys: set[str] = set(DYNAMIC_KEYS)
    for path in SOURCE_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in LITERAL_PATTERNS:
            keys.update(match.group(1) for match in pattern.finditer(source))
    return keys


def main() -> int:
    used = collect_used_keys()
    problems = 0
    tables: dict[str, dict[str, str]] = {}

    for path in sorted(LOCALES.glob("*.json")):
        tables[path.stem] = json.loads(path.read_text(encoding="utf-8"))

    if not tables:
        print("No locale files found.")
        return 1

    for code, table in tables.items():
        missing = sorted(used - table.keys())
        if missing:
            problems += len(missing)
            print(f"[{code}] missing {len(missing)} key(s):")
            for key in missing:
                print(f"    {key}")

    english = tables.get("en", {})
    for code, table in tables.items():
        if code == "en":
            continue
        extra = sorted(table.keys() - english.keys())
        if extra:
            print(f"[{code}] {len(extra)} key(s) not present in en.json: {', '.join(extra)}")
            problems += len(extra)
        untranslated = sorted(
            k for k, v in table.items()
            if english.get(k) == v and len(v) > 4 and k not in IDENTICAL_OK
        )
        if untranslated:
            print(f"[{code}] {len(untranslated)} key(s) identical to English "
                  f"(check if intentional): {', '.join(untranslated[:10])}")

    unused = sorted(english.keys() - used)
    if unused:
        print(f"[info] {len(unused)} key(s) defined but never used: {', '.join(unused)}")

    if problems:
        print(f"\nFAILED — {problems} problem(s).")
        return 1
    print(f"OK — {len(used)} keys present in all {len(tables)} locale(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
