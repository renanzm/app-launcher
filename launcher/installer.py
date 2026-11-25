"""Local installation: safe extraction, single-file apps and the launch environment."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from .config import AppConfig
from .i18n import tr


class AppInUseError(RuntimeError):
    """A file of the installation is locked, usually because the app is running."""


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _entry_parts(name: str) -> tuple:
    return PurePosixPath(name.replace("\\", "/")).parts


def common_root(names, executable: str = "") -> str:
    """The single top-level folder every entry lives in ('' if there is none).

    Release zips are often built as `MyApp-v1.2/…`; that folder is dropped on
    extraction, unless the configured executable already includes it.
    """
    roots = set()
    has_nested_file = False
    for name in names:
        parts = _entry_parts(name)
        if not parts:
            continue
        if len(parts) == 1 and not name.endswith("/"):
            return ""                       # a file at the top level: no common folder
        roots.add(parts[0])
        has_nested_file = has_nested_file or (len(parts) > 1 and not name.endswith("/"))
    if len(roots) != 1 or not has_nested_file:
        return ""
    root = roots.pop()
    exe_parts = _entry_parts(executable) if executable else ()
    if exe_parts and len(exe_parts) > 1 and exe_parts[0].lower() == root.lower():
        return ""
    return root


def safe_extract_zip(zip_path: Path, dest_dir: Path, on_progress=None, strip_root: str = ""):
    """Extracts `zip_path` into `dest_dir`, refusing entries outside the destination (Zip Slip).

    With `strip_root`, that leading folder is removed from every entry.
    """
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
            if strip_root:
                stripped = _entry_parts(normalized)[1:]
                if not stripped:
                    continue
                normalized = "/".join(stripped) + ("/" if member.is_dir() else "")
            target = (dest_dir / normalized).resolve()
            if not target.is_relative_to(dest_dir):
                raise ValueError(tr("Unsafe zip entry (outside the destination): {name}", name=member.filename))
            try:
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            except PermissionError as exc:
                raise AppInUseError(tr("Could not replace {name}: the file is in use. "
                                       "Close the application and try again.", name=target.name)) from exc
            if on_progress is not None:
                on_progress(index * 100 // total if total else 100)


# ---------------------------------------------------------------------------
# Install paths
# ---------------------------------------------------------------------------

def resolve_root(base_dir: Path, install_root: str = "") -> Path:
    """Folder where apps are installed: `install_root` (env vars allowed, relative to the launcher) or the launcher folder."""
    if not install_root:
        return Path(base_dir)
    path = Path(os.path.expandvars(os.path.expanduser(install_root)))
    return path if path.is_absolute() else Path(base_dir) / path


def install_path(base_dir: Path, app: AppConfig) -> Path:
    return Path(base_dir) / app.install_dir


def executable_for(app: AppConfig, record: dict | None = None) -> str:
    """The configured executable, or the one detected when the app was installed."""
    return app.executable or str((record or {}).get("executable") or "")


def is_installed(base_dir: Path, app: AppConfig, executable: str = "") -> bool:
    exe = executable or app.executable
    return bool(exe) and (install_path(base_dir, app) / exe).is_file()


def count_files(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(1 for p in folder.rglob("*") if p.is_file())


def folder_size(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    total = 0
    for p in folder.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def _simplify(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def find_executable(folder: Path, app: AppConfig) -> str:
    """Best guess of the app's .exe inside `folder` (relative path, '' if none).

    Prefers top-level executables whose name resembles the app or repository
    name, and skips uninstallers and helpers.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return ""
    wanted = {_simplify(app.name), _simplify(app.github.split("/")[-1]) if app.github else "", _simplify(app.id)}
    wanted.discard("")
    best, best_score = "", None
    for exe in folder.rglob("*.exe"):
        rel = exe.relative_to(folder)
        stem = _simplify(exe.stem)
        score = -len(rel.parts) * 10                      # shallower is better
        if stem in wanted:
            score += 100
        elif any(w and (w in stem or stem in w) for w in wanted):
            score += 50
        if re.search(r"unins|uninstall|setup|update|crash|helper|vc_?redist", exe.stem, re.I):
            score -= 80
        try:
            score += min(exe.stat().st_size // (1024 * 1024), 20)   # bigger is more likely the app
        except OSError:
            pass
        if best_score is None or score > best_score:
            best, best_score = rel.as_posix(), score
    return best


def install_package(zip_path: Path, dest: Path, on_progress=None, executable: str = ""):
    """Extracts the package into `dest` (files already there that are not in the package are kept)."""
    with zipfile.ZipFile(zip_path) as zf:
        root = common_root([m.filename for m in zf.infolist()], executable)
    safe_extract_zip(zip_path, Path(dest), on_progress=on_progress, strip_root=root)


def install_download(downloaded: Path, dest: Path, app: AppConfig, on_progress=None) -> str:
    """Installs a downloaded .zip or .exe into `dest`; returns the executable (relative path)."""
    downloaded, dest = Path(downloaded), Path(dest)
    suffix = downloaded.suffix.lower()
    if suffix == ".zip" or zipfile.is_zipfile(downloaded):
        install_package(downloaded, dest, on_progress=on_progress, executable=app.executable)
        executable = app.executable or find_executable(dest, app)
        if not executable:
            raise FileNotFoundError(tr("The package of {name} has no .exe file.", name=app.name))
        return executable
    if suffix == ".exe":
        name = app.executable or downloaded.name
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(downloaded, target)
        except PermissionError as exc:
            raise AppInUseError(tr("Could not replace {name}: the file is in use. "
                                   "Close the application and try again.", name=target.name)) from exc
        except OSError:
            shutil.copyfile(downloaded, target)        # different drive
            downloaded.unlink(missing_ok=True)
        if on_progress is not None:
            on_progress(100)
        return name
    raise ValueError(tr("{name} cannot be installed: only .zip and .exe files are supported.",
                        name=downloaded.name))


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
    # PyInstaller one-file builds export _MEI*/_PYI* variables; a child that is
    # itself a PyInstaller app must not inherit them.
    env = {k: v for k, v in env.items() if not k.startswith(("_MEI", "_PYI"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return subprocess.Popen([str(executable)], cwd=str(executable.parent), env=env)
