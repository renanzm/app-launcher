"""Instalação local: extração segura, builds personalizadas e ambiente de execução."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from .config import AppConfig
from .i18n import tr

# Metadados gravados dentro da pasta de cada build personalizada.
BUILD_META_FILE = ".launcher-build.json"


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

def safe_extract_zip(zip_path: Path, dest_dir: Path, on_progress=None):
    """Extrai `zip_path` em `dest_dir` recusando entradas fora do destino (Zip Slip)."""
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
# Caminhos de instalação
# ---------------------------------------------------------------------------

def install_path(base_dir: Path, app: AppConfig) -> Path:
    return Path(base_dir) / app.install_dir


def is_installed(base_dir: Path, app: AppConfig) -> bool:
    return (install_path(base_dir, app) / app.executable).is_file()


def count_files(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(1 for p in folder.rglob("*") if p.is_file())


# ---------------------------------------------------------------------------
# Builds personalizadas (entregas por ticket, em pastas isoladas)
# ---------------------------------------------------------------------------

def build_dir(base_dir: Path, app: AppConfig, code: str) -> Path:
    return Path(base_dir) / f"{app.install_dir} - build {code}"


def pick_package_name(files, candidates) -> str | None:
    """Primeiro nome de `candidates` presente em `files` (comparação exata)."""
    available = set(files)
    return next((name for name in candidates if name in available), None)


def is_valid_code(code: str, pattern: str) -> bool:
    return bool(code) and re.fullmatch(pattern, code) is not None


def read_build_meta(folder: Path) -> dict | None:
    try:
        data = json.loads((Path(folder) / BUILD_META_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def write_build_meta(folder: Path, code: str, info: dict, mdtm: str, size: int):
    meta = {
        "code": code,
        "id": info.get("id", ""),
        "description": info.get("description", ""),
        "base_version": info.get("base_version", ""),
        "date": info.get("date", ""),
        "mdtm": mdtm,
        "size": size,
        "installed_at": datetime.now().isoformat(timespec="seconds"),
    }
    (Path(folder) / BUILD_META_FILE).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_builds(base_dir: Path, app: AppConfig) -> list[dict]:
    """Builds personalizadas instaladas (pastas com o executável principal)."""
    prefix = f"{app.install_dir} - build "
    builds = []
    try:
        children = sorted(Path(base_dir).iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return builds
    for child in children:
        if not (child.is_dir() and child.name.startswith(prefix)):
            continue
        if not (child / app.executable).is_file():
            continue
        meta = read_build_meta(child) or {}
        builds.append({**meta, "code": meta.get("code") or child.name[len(prefix):],
                       "folder": str(child)})
    return builds


def carry_over_files(source_dir: Path | None, target_dir: Path, names) -> list[str]:
    """Copia da instalação oficial os arquivos listados (ex.: configurações do usuário).

    Retorna os nomes efetivamente copiados.
    """
    if source_dir is None or not Path(source_dir).is_dir():
        return []
    copied = []
    for name in names:
        source = Path(source_dir) / name
        if source.is_file():
            target = Path(target_dir) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(name)
    return copied


def install_package(zip_path: Path, dest: Path, clean: bool = False, on_progress=None):
    """Extrai o pacote. `clean=True` apaga o destino antes (usado em builds)."""
    dest = Path(dest)
    if clean and dest.exists():
        shutil.rmtree(dest)
    safe_extract_zip(zip_path, dest, on_progress=on_progress)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def build_launch_env(app: AppConfig, option_values: dict, session: dict | None = None,
                     base_env: dict | None = None) -> dict:
    """Ambiente do processo filho: herdado + `env` do app + opções + sessão.

    - opções booleanas ligadas viram "1"; desligadas removem a variável;
    - opções de texto vazias removem a variável (nada de valor obsoleto herdado);
    - `session` mapeia nome da variável → valor (usuário/senha do login).
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
