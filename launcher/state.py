"""Estado persistente do launcher (preferências, versões instaladas, segredos).

Fica em `%LOCALAPPDATA%\\<app_id>\\state.json` — por usuário do Windows, fora
da pasta de instalação e sem depender do Registro. Segredos (senha lembrada,
credenciais do servidor em cache) são cifrados com a DPAPI do Windows antes de
serem gravados, então só o mesmo usuário Windows consegue lê-los.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# DPAPI (CryptProtectData) — sem dependências externas
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes.wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", ctypes.wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _dpapi(data: bytes, protect: bool):
        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = _Blob(len(data), buf)
        blob_out = _Blob()
        fn = (ctypes.windll.crypt32.CryptProtectData if protect
              else ctypes.windll.crypt32.CryptUnprotectData)
        if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
else:  # pragma: no cover - o launcher é Windows-only; isto só mantém o import.
    def _dpapi(data: bytes, protect: bool):
        return None


def protect(plaintext: str) -> str | None:
    """Cifra com DPAPI e devolve base64 (None se a DPAPI falhar)."""
    raw = _dpapi(plaintext.encode("utf-8"), protect=True)
    return base64.b64encode(raw).decode("ascii") if raw is not None else None


def unprotect(token: str) -> str | None:
    try:
        raw = _dpapi(base64.b64decode(token), protect=False)
        return raw.decode("utf-8") if raw is not None else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Arquivo de estado
# ---------------------------------------------------------------------------

def default_state_path(app_id: str) -> Path:
    root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(root) / app_id / "state.json"


class StateStore:
    """Dicionário persistido em JSON, gravado de forma atômica a cada mudança."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = self._read()

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".state-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # -- acesso genérico por seção/chave --------------------------------
    def get(self, section: str, key: str, default=None):
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value):
        bucket = self._data.setdefault(section, {})
        if bucket.get(key) == value:
            return
        bucket[key] = value
        self._write()

    def delete(self, section: str, key: str):
        if key in self._data.get(section, {}):
            del self._data[section][key]
            self._write()

    # -- preferências ----------------------------------------------------
    def pref(self, key: str, default=False):
        return self.get("preferences", key, default)

    def set_pref(self, key: str, value):
        self.set("preferences", key, value)

    def app_option(self, app_id: str, key: str, default=None):
        return self.get("app_options", f"{app_id}.{key}", default)

    def set_app_option(self, app_id: str, key: str, value):
        self.set("app_options", f"{app_id}.{key}", value)

    def option_value(self, app_id: str, option):
        """Valor de uma opção de app; as do tipo "password" ficam cifradas."""
        if option.type == "password":
            value = self.secret(f"option.{app_id}.{option.key}")
            return option.default if value is None else value
        return self.app_option(app_id, option.key, option.default)

    def set_option_value(self, app_id: str, option, value):
        if option.type == "password":
            self.set_secret(f"option.{app_id}.{option.key}", str(value or ""))
        else:
            self.set_app_option(app_id, option.key, value)

    def option_values(self, app) -> dict:
        return {o.key: self.option_value(app.id, o) for o in app.options}

    # -- versão instalada (MDTM|SIZE) ------------------------------------
    def install_record(self, key: str):
        """Retorna (mdtm, size) ou None."""
        raw = self.get("installed", key)
        if isinstance(raw, dict) and raw.get("mdtm"):
            try:
                return str(raw["mdtm"]), int(raw.get("size") or 0)
            except (TypeError, ValueError):
                return None
        return None

    def set_install_record(self, key: str, mdtm: str, size: int):
        self.set("installed", key, {"mdtm": mdtm, "size": int(size)})

    def clear_install_record(self, key: str):
        self.delete("installed", key)

    # -- segredos (DPAPI) ------------------------------------------------
    def secret(self, key: str) -> str | None:
        token = self.get("secrets", key)
        return unprotect(token) if token else None

    def set_secret(self, key: str, value: str) -> bool:
        token = protect(value)
        if token is None:
            return False
        self.set("secrets", key, token)
        return True

    def delete_secret(self, key: str):
        self.delete("secrets", key)
