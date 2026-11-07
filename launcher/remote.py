"""Access to the distribution server (FTP or FTPS).

Covers: credential resolution, connection, metadata queries (MDTM/SIZE),
directory listing and download with progress and optional SHA-256
verification (`<file>.sha256` next to the file on the server).
"""

from __future__ import annotations

import ftplib
import hashlib
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import crypto
from .config import ServerConfig
from .i18n import language, tr

_CACHE_KEY = "server_credentials"


class CredentialsError(RuntimeError):
    """The server credentials cannot be obtained."""


class IntegrityError(RuntimeError):
    """The downloaded file does not match the published size/hash."""


@dataclass(frozen=True)
class Credentials:
    host: str
    port: int
    user: str
    password: str


@dataclass(frozen=True)
class RemoteFile:
    name: str
    mdtm: str | None
    size: int | None
    directory: str = ""
    badge: str = ""


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def _password_from(data: dict, secret: str) -> str:
    if data.get("password_enc"):
        if not secret:
            raise CredentialsError(tr("password_enc is set, but server.secret is empty."))
        return crypto.decrypt(data["password_enc"], secret)
    return str(data.get("password") or "")


def _fetch_remote_credentials(url: str, timeout: int = 5) -> dict:
    import requests

    # A varying parameter keeps a CDN from returning an old version of the JSON.
    response = requests.get(
        url, params={"_": int(time.time())},
        headers={"Cache-Control": "no-cache"}, timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not data.get("host"):
        raise ValueError(tr("Credentials JSON has no 'host'."))
    return data


def resolve_credentials(server: ServerConfig, store=None, fetch=_fetch_remote_credentials) -> Credentials:
    """Effective server credentials.
    
    Without `credentials_url`, uses what is in the configuration. With it, the
    remote JSON is the source of truth; the last valid response is cached
    (encrypted with DPAPI) so the launcher works when the URL is down.
    """
    if not server.credentials_url:
        return Credentials(
            host=server.host, port=server.port, user=server.user,
            password=_password_from(
                {"password": server.password, "password_enc": server.password_enc},
                server.secret,
            ),
        )

    try:
        data = fetch(server.credentials_url)
        creds = Credentials(
            host=str(data["host"]),
            port=int(data.get("port") or server.port),
            user=str(data.get("user") or server.user),
            password=_password_from(data, server.secret),
        )
    except Exception:
        cached = store.secret(_CACHE_KEY) if store is not None else None
        if cached:
            try:
                return Credentials(**json.loads(cached))
            except (TypeError, ValueError):
                pass
        raise CredentialsError(
            tr("Could not get the server credentials and there are no saved "
               "credentials on this machine. Check your internet connection.")
        ) from None

    if store is not None:
        store.set_secret(_CACHE_KEY, json.dumps(creds.__dict__))
    return creds


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

class RemoteServer:
    def __init__(self, server: ServerConfig, store=None):
        self.server = server
        self.store = store

    @contextmanager
    def connect(self):
        creds = resolve_credentials(self.server, self.store)
        ftp_cls = ftplib.FTP_TLS if self.server.protocol == "ftps" else ftplib.FTP
        ftp = ftp_cls(timeout=self.server.timeout, encoding=self.server.encoding)
        try:
            ftp.connect(creds.host, creds.port)
            ftp.login(creds.user, creds.password)
            if isinstance(ftp, ftplib.FTP_TLS):
                ftp.prot_p()
            ftp.voidcmd("TYPE I")
            yield ftp
        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()


# ---------------------------------------------------------------------------
# Operations (take an already-connected ftplib.FTP)
# ---------------------------------------------------------------------------

def try_cwd(ftp, path: str) -> bool:
    try:
        ftp.cwd(path)
        return True
    except ftplib.error_perm:
        return False


def stat(ftp, name: str) -> RemoteFile:
    """MDTM + SIZE of a file in the current directory. Raises error_perm if it does not exist."""
    mdtm = ftp.sendcmd(f"MDTM {name}").split()[1]
    size = ftp.size(name)
    return RemoteFile(name=name, mdtm=mdtm, size=int(size) if size is not None else None)


def read_text(ftp, name: str, max_bytes: int = 1_000_000) -> str | None:
    """Text content of a small file; None if it does not exist."""
    buf = bytearray()

    def collect(chunk):
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise ValueError(tr("{name} exceeds {max} bytes", name=name, max=max_bytes))

    try:
        ftp.retrbinary(f"RETR {name}", collect)
    except ftplib.error_perm:
        return None
    return bytes(buf).decode("utf-8-sig")


def _parse_sha256(text: str | None) -> str | None:
    """Accepts both `<hash>` and the sha256sum format (`<hash>  file`)."""
    if not text:
        return None
    token = text.strip().split()[0].lower() if text.strip() else ""
    if len(token) == 64 and all(c in "0123456789abcdef" for c in token):
        return token
    return None


def download(ftp, name: str, target: Path, expected_size: int | None = None,
             on_progress=None, verify_hash: bool = True) -> Path:
    """Downloads `name` (from the current directory) to `target`, safely.
    
    Writes to `<target>.part` and only renames at the end, after checking the
    size and — if the server publishes `<name>.sha256` — the hash.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    done = 0

    expected_hash = _parse_sha256(read_text(ftp, f"{name}.sha256")) if verify_hash else None

    try:
        with open(partial, "wb") as f:
            def write(chunk):
                nonlocal done
                f.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if on_progress and expected_size:
                    on_progress(min(100, done * 100 // expected_size))

            ftp.retrbinary(f"RETR {name}", write, blocksize=64 * 1024)

        if expected_size and done != expected_size:
            raise IntegrityError(
                f"Download incompleto de {name}: {done} de {expected_size} bytes."
            )
        if expected_hash and digest.hexdigest() != expected_hash:
            raise IntegrityError(tr("The SHA-256 of {name} does not match the one published on the server.", name=name))
        partial.replace(target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return target


def list_files(ftp) -> list[RemoteFile]:
    """Files in the current directory. Uses MLSD and falls back to NLST+SIZE+MDTM."""
    directory = ftp.pwd()
    try:
        entries = []
        for name, facts in ftp.mlsd(facts=["type", "size", "modify"]):
            if name in (".", "..") or (facts.get("type") or "").lower() in ("dir", "cdir", "pdir"):
                continue
            try:
                size = int(facts["size"]) if facts.get("size") else None
            except ValueError:
                size = None
            entries.append(RemoteFile(name, facts.get("modify"), size, directory))
        return entries
    except (ftplib.error_perm, ftplib.error_proto):
        pass

    entries = []
    for raw in ftp.nlst():
        name = raw.rsplit("/", 1)[-1]
        if not name or name in (".", ".."):
            continue
        try:
            size = ftp.size(name)
        except ftplib.all_errors:
            size = None
        try:
            mdtm = ftp.sendcmd(f"MDTM {name}").split()[1]
        except ftplib.all_errors:
            mdtm = None
        # Directories usually fail SIZE and MDTM; files rarely fail both.
        if size is None and mdtm is None:
            try:
                ftp.cwd(name)
                ftp.cwd(directory)
                continue
            except ftplib.error_perm:
                pass
        entries.append(RemoteFile(name, mdtm, size, directory))
    return entries


def file_info(ftp, directory: str, name: str) -> RemoteFile:
    """Metadata of a file in another directory; fields are None if unavailable."""
    saved = ftp.pwd()
    try:
        if not try_cwd(ftp, directory):
            return RemoteFile(name, None, None, directory)
        for entry in list_files(ftp):
            if entry.name.lower() == name.lower():
                return RemoteFile(entry.name, entry.mdtm, entry.size, directory)
        return RemoteFile(name, None, None, directory)
    finally:
        try_cwd(ftp, saved)


def format_mdtm(mdtm: str | None) -> str:
    """MDTM (UTC, YYYYMMDDHHMMSS[.fff]) -> local time: 'YYYY-MM-DD hh:mm' (en) or 'dd/mm/yyyy hh:mm' (pt-BR)."""
    if not mdtm:
        return "—"
    try:
        dt = datetime.strptime(mdtm[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%d/%m/%Y %H:%M" if language() == "pt-BR" else "%Y-%m-%d %H:%M")
    except ValueError:
        return mdtm


def format_size(n_bytes: int | None) -> str:
    if n_bytes is None:
        return "—"
    value = float(n_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
