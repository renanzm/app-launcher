"""Servidor FTP local com aplicativos de exemplo, para testar o launcher.

Uso:
    pip install -r requirements-dev.txt
    python -m tools.demo_server            # escuta em 127.0.0.1:2121 (demo/demo)
    python -m launcher                     # em outro terminal

Os arquivos são gerados em `demo-server/` (ignorado pelo git). Rode com
`--bump` para publicar uma "versão nova" dos apps e testar a atualização.
"""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "demo-server"

_APP_BAT = """@echo off
title {title}
echo.
echo   {title} foi iniciado pelo launcher.
echo.
echo   NOTES_LAUNCHED_BY = %NOTES_LAUNCHED_BY%
echo   NOTES_VERBOSE     = %NOTES_VERBOSE%
echo   NOTES_WORKSPACE   = %NOTES_WORKSPACE%
echo   Pasta atual       = %CD%
echo.
pause
"""


def _zip(path: Path, files: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="ascii")


def build_tree(version: str):
    _zip(ROOT / "apps" / "notes" / "notes.zip", {
        "notes.bat": _APP_BAT.format(title=f"Notes Studio {version}"),
        "diagnostics.bat": _APP_BAT.format(title="Notes Studio - Diagnostico"),
        "settings.ini": "[general]\ntheme=dark\n",
        "README.txt": f"Notes Studio {version}\n",
    })
    build = ROOT / "apps" / "notes" / "custom-builds" / "12345"
    _zip(build / "build.zip", {
        "notes.bat": _APP_BAT.format(title="Notes Studio - build do ticket 12345"),
        "settings.ini": "[general]\ntheme=light\n",
    })
    (build / "info.json").write_text(json.dumps({
        "id": "2026-11-02-12345",
        "description": "Correção do salvamento automático relatada no ticket 12345.",
        "base_version": version,
        "date": "2026-11-02",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    _zip(ROOT / "apps" / "reports" / "reports.zip", {
        "reports.bat": _APP_BAT.format(title=f"Reports Viewer {version}"),
    })
    (ROOT / "apps" / "reports" / "sample-data.csv").write_text("id,value\n1,42\n", encoding="utf-8")

    tools = ROOT / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "cleanup-script.ps1").write_text("Write-Host 'cleanup'\n", encoding="utf-8")
    (tools / "log-collector.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    installers = ROOT / "installers"
    installers.mkdir(parents=True, exist_ok=True)
    (installers / "runtime-setup.msi").write_bytes(b"\x00" * 2048)
    (ROOT / "launcher").mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=2121)
    parser.add_argument("--bump", action="store_true", help="republica os pacotes como versão nova")
    parser.add_argument("--version", default="1.0")
    args = parser.parse_args()

    if args.bump or not (ROOT / "apps").exists():
        build_tree("1.1" if args.bump else args.version)

    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer

    authorizer = DummyAuthorizer()
    authorizer.add_user("demo", "demo", str(ROOT), perm="elr")
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.passive_ports = range(60000, 60100)
    server = FTPServer(("127.0.0.1", args.port), handler)
    print(f"Servidor de demonstração em ftp://demo:demo@127.0.0.1:{args.port} ({ROOT})")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
