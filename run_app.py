#!/usr/bin/env python3
"""Launch the TRAVKOD PyQt6 desktop app: ``python run_app.py``.

Before importing the app, we check that the runtime dependencies are installed
and print a clear, actionable message if any are missing (instead of a raw
ModuleNotFoundError deep in the import chain).
"""
import importlib.util
import os
import sys

# (import name, pip package) for the hard runtime requirements.
_REQUIRED = [
    ("PyQt6", "PyQt6"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("soundfile", "soundfile"),
    ("pyloudnorm", "pyloudnorm"),
]

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "python"))


def _check_deps() -> None:
    missing = [pkg for mod, pkg in _REQUIRED if importlib.util.find_spec(mod) is None]
    if not missing:
        return
    req = os.path.join("python", "requirements.txt")
    print("TRAVKOD: missing required package(s): " + ", ".join(missing), file=sys.stderr)
    print("", file=sys.stderr)
    print("Install everything with:", file=sys.stderr)
    print(f'    "{sys.executable}" -m pip install -r {req}', file=sys.stderr)
    print("", file=sys.stderr)
    print("or just the missing ones:", file=sys.stderr)
    print(f'    "{sys.executable}" -m pip install {" ".join(missing)}', file=sys.stderr)
    if sys.version_info >= (3, 13):
        print("", file=sys.stderr)
        print(f"Note: you are on Python {sys.version_info.major}.{sys.version_info.minor}. "
              "If pip can't find wheels for a package, Python 3.11 or 3.12 has the "
              "widest prebuilt-wheel coverage for the audio stack.", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    _check_deps()
    from travkod_app.app import main as app_main
    return app_main()


if __name__ == "__main__":
    sys.exit(main())
