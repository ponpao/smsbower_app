"""Download Kantumruy Pro (regular + bold statics) into assets/fonts/.

Run once before building the .exe so the font is bundled. If this script
can't run (offline build), the app falls back to Segoe UI automatically.
"""

from __future__ import annotations

from pathlib import Path

import requests

FILES = {
    "KantumruyPro-Regular.ttf":
        "https://raw.githubusercontent.com/google/fonts/main/ofl/kantumruypro/KantumruyPro%5Bwght%5D.ttf",
}

# The upstream file is a variable font covering all weights; Qt handles it.


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dest = out_dir / name
        print(f"downloading {name} …")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        if not resp.content[:4] in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
            raise SystemExit(f"{name}: response is not a TTF (blocked network?)")
        dest.write_bytes(resp.content)
        print(f"  -> {dest} ({len(resp.content) // 1024} KiB)")


if __name__ == "__main__":
    main()
