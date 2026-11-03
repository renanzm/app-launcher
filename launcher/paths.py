"""Pastas usadas pelo launcher, nos modos script e .exe (PyInstaller)."""

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Pasta do .exe: onde ficam os apps instalados e o launcher_config.json.
    BASE_DIR = Path(sys.executable).resolve().parent
    # Recursos embutidos via --add-data (extraídos em _MEIPASS).
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR


def resource_path(relative: str) -> Path:
    return BUNDLE_DIR / relative
