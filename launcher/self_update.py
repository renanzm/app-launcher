"""Atualização do próprio launcher (somente no .exe empacotado).

Fluxo: baixa `<exe>.new.exe`, grava um .bat que espera este processo sair,
troca os arquivos e reabre o launcher com `--applied-self-update <mdtm> <size>`.
Na reabertura, a versão só é registrada se o executável em disco tiver mesmo
o tamanho novo — se a troca falhou (antivírus, permissão, outra instância
aberta), o registro não muda e a atualização é tentada na próxima abertura.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MARKER = "--applied-self-update"
RECORD_KEY = "__launcher__"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def running_exe_size() -> int | None:
    if not is_frozen():
        return None
    try:
        return Path(sys.executable).stat().st_size
    except OSError:
        return None


def leftover_paths(exe: Path):
    exe = Path(exe)
    return (exe.with_name(f"{exe.stem}.old.exe"),
            exe.with_name(f"{exe.stem}.new.exe"),
            exe.with_name("_update_launcher.bat"))


def cleanup_leftovers():
    if not is_frozen():
        return
    for path in leftover_paths(Path(sys.executable)):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def consume_applied_args(argv: list, store, exe_size=running_exe_size):
    """Remove o marcador de argv. Retorna (argv_limpo, falhou)."""
    if MARKER not in argv:
        return argv, False
    idx = argv.index(MARKER)
    failed = False
    try:
        mdtm, size = argv[idx + 1], int(argv[idx + 2])
        if mdtm and size:
            if exe_size() == size:
                store.set_install_record(RECORD_KEY, mdtm, size)
            else:
                failed = True
    except (IndexError, ValueError):
        pass
    cleanup_leftovers()
    return argv[:idx] + argv[idx + 3:], failed


def needs_update(record, remote_mdtm: str, remote_size: int, local_size: int | None) -> bool:
    """Compara o .exe publicado com o registro local.

    Sem registro (primeira execução), um tamanho igual ao publicado é tomado
    como "já atualizado" — o chamador então só grava o registro.
    """
    if record:
        return not (record[0] == remote_mdtm and record[1] == remote_size)
    return local_size != remote_size


def build_swap_script(exe: Path, new: Path, old: Path, pid: int, mdtm: str, size: int) -> str:
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        f"set \"PID={pid}\"\r\n"
        f"set \"DST={exe}\"\r\n"
        f"set \"NEW={new}\"\r\n"
        f"set \"OLD={old}\"\r\n"
        ":wait\r\n"
        "tasklist /FI \"PID eq %PID%\" | find \"%PID%\" >nul\r\n"
        "if not errorlevel 1 (\r\n"
        "  ping 127.0.0.1 -n 2 >nul\r\n"
        "  goto wait\r\n"
        ")\r\n"
        "ping 127.0.0.1 -n 3 >nul\r\n"
        "set /a N=0\r\n"
        ":retry\r\n"
        "set /a N+=1\r\n"
        "if exist \"%DST%\" copy /Y \"%DST%\" \"%OLD%\" >nul 2>&1\r\n"
        "move /Y \"%NEW%\" \"%DST%\" >nul 2>&1\r\n"
        "if exist \"%NEW%\" (\r\n"
        "  if %N% LSS 15 (\r\n"
        "    ping 127.0.0.1 -n 2 >nul\r\n"
        "    goto retry\r\n"
        "  )\r\n"
        ")\r\n"
        "set \"PYINSTALLER_RESET_ENVIRONMENT=1\"\r\n"
        f"start \"\" \"%DST%\" {MARKER} {mdtm} {int(size)}\r\n"
        "del \"%~f0\"\r\n"
    )


def apply(new_exe: Path, mdtm: str, size: int):
    """Grava o .bat de troca e o dispara desacoplado. O chamador deve encerrar o app."""
    exe = Path(sys.executable)
    _, _, bat = leftover_paths(exe)
    old = exe.with_name(f"{exe.stem}.old.exe")
    bat.write_text(build_swap_script(exe, new_exe, old, os.getpid(), mdtm, size), encoding="ascii")

    # O .exe --onefile do PyInstaller exporta _MEIPASS/_PYI*; se o novo processo
    # herdar essas variáveis, tenta usar a pasta temporária do processo antigo.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("_MEI", "_PYI"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)], cwd=str(exe.parent), env=env, creationflags=flags,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True,
    )
