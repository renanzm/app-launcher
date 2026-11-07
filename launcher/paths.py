"""Folders used by the launcher, in script and .exe (PyInstaller) modes."""

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # .exe folder: where installed apps and launcher_config.json live.
    BASE_DIR = Path(sys.executable).resolve().parent
    # Resources bundled via --add-data (extracted to _MEIPASS).
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR


def resource_path(relative: str) -> Path:
    return BUNDLE_DIR / relative
