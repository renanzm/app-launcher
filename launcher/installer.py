"""Local installation: safe extraction and the launch environment."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from .config import AppConfig
from .i18n import tr


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def safe_extract_zip(zip_path: Path, dest_dir: Path, on_progress=None):
    """Extracts `zip_path` into `dest_dir`, refusing entries outside the destination (Zip Slip)."""
    dest_dir = Path(dest_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.infolist()
        total = len(members)
        for index, member in enumerate(members, start=1):
            normalized = member.filename.replace("\\", "/")
            parts = Path(normalized).parts
            if (not normalized or normalized.startswith("/") or ".." in parts
                    or re.match(r"^[A-Za-z]:", normalized)):
                raise ValueError(tr("Unsafe zip entry: {name}", name=member.filename))
            target = (dest_dir / normalized).resolve()
            if not target.is_relative_to(dest_dir):
                raise ValueError(tr("Unsafe zip entry (outside the destination): {name}", name=member.filename))
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            if on_progress is not None:
                on_progress(index * 100 // total if total else 100)


# ---------------------------------------------------------------------------
# Install paths
# ---------------------------------------------------------------------------

def install_path(base_dir: Path, app: AppConfig) -> Path:
    return Path(base_dir) / app.install_dir


def is_installed(base_dir: Path, app: AppConfig) -> bool:
    return (install_path(base_dir, app) / app.executable).is_file()


def count_files(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(1 for p in folder.rglob("*") if p.is_file())


def install_package(zip_path: Path, dest: Path, on_progress=None):
    """Extracts the package into `dest`."""
    safe_extract_zip(zip_path, Path(dest), on_progress=on_progress)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def build_launch_env(app: AppConfig, option_values: dict, session: dict | None = None,
                     base_env: dict | None = None) -> dict:
    """Child process environment: inherited + the app's `env` + options + session.
    
    - enabled boolean options become "1"; disabled ones remove the variable;
    - empty text options remove the variable (no stale inherited value);
    - `session` maps variable name -> value (the login's user/password).
    """
    env = dict(os.environ if base_env is None else base_env)
    env.update(app.env)
    for option in app.options:
        if not option.env:
            continue
        value = option_values.get(option.key, option.default)
        if option.type == "bool":
            if value:
                env[option.env] = "1"
            else:
                env.pop(option.env, None)
        else:
            text = "" if value is None else str(value)
            if text:
                env[option.env] = text
            else:
                env.pop(option.env, None)
    for name, value in (session or {}).items():
        if not name:
            continue
        if value:
            env[name] = value
        else:
            env.pop(name, None)
    return env


def launch(executable: Path, env: dict) -> subprocess.Popen:
    executable = Path(executable)
    if not executable.is_file():
        raise FileNotFoundError(tr("Executable not found: {name}", name=executable))
    return subprocess.Popen([str(executable)], cwd=str(executable.parent), env=env)
