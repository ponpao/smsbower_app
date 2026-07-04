#!/usr/bin/env python3
"""Launch the TRAVKOD PyQt6 desktop app: `python run_app.py`."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "python"))
from travkod_app.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
