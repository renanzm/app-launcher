"""GitHub Releases: applications published as release assets on GitHub.

Uses the REST API with conditional requests: every response is cached on disk
with its ETag, so repeated checks are answered with 304 (which does not count
against the rate limit) and the launcher keeps working offline with the last
data it saw. Downloads are checked against the size and the SHA-256 digest
that GitHub publishes for each asset.

No Qt here; the interface calls this from background threads.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .i18n import tr

API_URL = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = "app-launcher (+https://github.com/renanzm/app-launcher)"
INSTALLABLE_SUFFIXES = (".zip", ".exe")
_CHUNK = 256 * 1024


class GitHubError(RuntimeError):
    """GitHub could not answer (network, permissions, missing repository…)."""


class RateLimitError(GitHubError):
    """The hourly API limit was reached."""

    def __init__(self, message: str, reset: datetime | None = None):
        super().__init__(message)
        self.reset = reset


class DownloadCancelled(Exception):
    """The user cancelled the download."""


class IntegrityError(RuntimeError):
    """The downloaded file does not match the published size/hash."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Asset:
    id: int
    name: str
    size: int | None
    download_url: str               # browser_download_url (public)
    api_url: str                    # API url (works with a token, also for private repos)
    digest: str | None = None       # lowercase hex SHA-256, when GitHub provides it
    updated: str = ""

    @property
    def kind(self) -> str:
        """'zip', 'exe' or '' (not installable)."""
        suffix = Path(self.name).suffix.lower()
        return suffix[1:] if suffix in INSTALLABLE_SUFFIXES else ""


@dataclass(frozen=True)
class Release:
    tag: str
    title: str
    notes: str                      # Markdown
    published: datetime | None
    url: str
    prerelease: bool
    assets: tuple = ()


@dataclass(frozen=True)
class Repository:
    full_name: str
    description: str = ""
    html_url: str = ""
    homepage: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    language: str = ""
    license: str = ""
    topics: tuple = ()
    archived: bool = False
    has_issues: bool = True


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_digest(value) -> str | None:
    text = str(value or "").strip().lower()
    if text.startswith("sha256:"):
        text = text[7:]
    return text if re.fullmatch(r"[0-9a-f]{64}", text) else None


def parse_asset(data: dict) -> Asset:
    return Asset(
        id=int(data.get("id") or 0),
        name=str(data.get("name") or ""),
        size=int(data["size"]) if data.get("size") is not None else None,
        download_url=str(data.get("browser_download_url") or ""),
        api_url=str(data.get("url") or ""),
        digest=_parse_digest(data.get("digest")),
        updated=str(data.get("updated_at") or ""),
    )


def parse_release(data: dict) -> Release:
    tag = str(data.get("tag_name") or "")
    return Release(
        tag=tag,
        title=str(data.get("name") or "").strip() or tag,
        notes=str(data.get("body") or ""),
        published=_parse_time(data.get("published_at") or data.get("created_at")),
        url=str(data.get("html_url") or ""),
        prerelease=bool(data.get("prerelease")),
        assets=tuple(parse_asset(a) for a in data.get("assets") or []
                     if a.get("state", "uploaded") == "uploaded"),
    )


def parse_repository(data: dict) -> Repository:
    license_ = data.get("license") or {}
    spdx = str(license_.get("spdx_id") or "")
    return Repository(
        full_name=str(data.get("full_name") or ""),
        description=str(data.get("description") or ""),
        html_url=str(data.get("html_url") or ""),
        homepage=str(data.get("homepage") or ""),
        stars=int(data.get("stargazers_count") or 0),
        forks=int(data.get("forks_count") or 0),
        open_issues=int(data.get("open_issues_count") or 0),
        language=str(data.get("language") or ""),
        license="" if spdx in ("", "NOASSERTION") else spdx,
        topics=tuple(data.get("topics") or ()),
        archived=bool(data.get("archived")),
        has_issues=bool(data.get("has_issues", True)),
    )


# ---------------------------------------------------------------------------
# Choosing the asset and comparing versions
# ---------------------------------------------------------------------------

def pick_asset(assets, pattern: str = "") -> Asset | None:
    """The asset to install.

    With `pattern` (a glob such as ``MyApp-*-windows.zip``), the first match.
    Without it, the most likely portable Windows build: a .zip or .exe that is
    not an installer and not for another platform; .zip wins a tie.
    """
    assets = list(assets)
    if pattern:
        wanted = pattern.lower()
        return next((a for a in assets if fnmatch.fnmatchcase(a.name.lower(), wanted)), None)

    def score(asset: Asset) -> int:
        name = asset.name.lower()
        value = 0
        if any(w in name for w in ("linux", "macos", "darwin", "osx", "-mac", "_mac")):
            value -= 50
        if any(w in name for w in ("setup", "installer")):
            value -= 10
        if any(w in name for w in ("arm64", "aarch64")):
            value -= 4
        if "win" in name:
            value += 3
        if any(w in name for w in ("x64", "amd64", "win64", "x86_64")):
            value += 2
        if name.endswith(".zip"):
            value += 1
        return value

    candidates = [a for a in assets if a.kind]
    if not candidates:
        return None
    best = max(candidates, key=score)
    return best if score(best) > -40 else None      # only builds for other platforms


def pick_icon_asset(assets, executable: str = "", installed: Asset | None = None) -> Asset | None:
    """The .exe asset whose icon best represents the app (None if the release has no .exe).

    Prefers the executable the app launches, then the installed asset itself;
    installers and uninstallers are skipped, since they often carry their own icon.
    """
    exes = [a for a in assets if a.kind == "exe"]
    wanted = Path(executable.replace("\\", "/")).name.lower() if executable else ""
    if wanted:
        match = next((a for a in exes if a.name.lower() == wanted), None)
        if match is not None:
            return match
    if installed is not None and installed.kind == "exe":
        return installed
    plain = [a for a in exes if not re.search(r"setup|install|unins|update", a.name, re.IGNORECASE)]
    return plain[0] if plain else None


_PRE_RELEASE = re.compile(r"^[\s._+-]*(a|alpha|b|beta|rc|pre|preview|dev|snapshot)", re.IGNORECASE)


def version_key(text: str):
    """(numbers, is_final) parsed from a tag such as 'v1.2.3' or 'release-2.0-rc1'; None if no number."""
    match = re.search(r"\d+(?:\.\d+)*", text or "")
    if not match:
        return None
    numbers = [int(n) for n in match.group(0).split(".")]
    final = not _PRE_RELEASE.match(text[match.end():])
    return numbers, final


def is_newer(candidate: str, current: str) -> bool:
    """True if `candidate` is a later version than `current` (unknown formats are never newer)."""
    a, b = version_key(candidate), version_key(current)
    if a is None or b is None:
        return False
    width = max(len(a[0]), len(b[0]))
    na = a[0] + [0] * (width - len(a[0]))
    nb = b[0] + [0] * (width - len(b[0]))
    return (na, a[1]) > (nb, b[1])


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class GitHubClient:
    """Small GitHub REST client with an on-disk ETag cache.

    Every method may run on a worker thread; each thread gets its own HTTP session.
    """

    def __init__(self, token: str = "", cache_dir: Path | None = None, timeout: int = 20,
                 api_url: str = API_URL, session_factory=None):
        self.token = token.strip()
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.timeout = timeout
        self.api_url = api_url.rstrip("/")
        self._api_host = urlparse(self.api_url).netloc.lower()
        self._session_factory = session_factory
        self._local = threading.local()

    # -- HTTP ------------------------------------------------------------
    def _session(self):
        session = getattr(self._local, "session", None)
        if session is None:
            if self._session_factory is not None:
                session = self._session_factory()
            else:
                import requests
                session = requests.Session()
            session.headers["User-Agent"] = USER_AGENT
            self._local.session = session
        return session

    def _headers(self, url: str, accept: str = "application/vnd.github+json") -> dict:
        headers = {"Accept": accept}
        # The token only ever goes to the API host, never to download mirrors or image hosts.
        if urlparse(url).netloc.lower() == self._api_host:
            headers["X-GitHub-Api-Version"] = API_VERSION
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _cache_path(self, kind: str, url: str, suffix: str = ".json") -> Path | None:
        if self.cache_dir is None:
            return None
        name = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self.cache_dir / kind / f"{name}{suffix}"

    @staticmethod
    def _read_cache(path: Path | None) -> dict | None:
        if path is None:
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and "data" in data else None
        except (OSError, ValueError):
            return None

    def _raise_for(self, response, what: str):
        status = response.status_code
        if status in (403, 429):
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining == "0" or status == 429 or response.headers.get("Retry-After"):
                reset = None
                try:
                    reset = datetime.fromtimestamp(int(response.headers.get("X-RateLimit-Reset") or 0)).astimezone()
                except (TypeError, ValueError, OSError):
                    pass
                when = reset.strftime("%H:%M") if reset and reset.year > 1970 else "?"
                raise RateLimitError(
                    tr("GitHub's request limit was reached. Try again after {time}.", time=when), reset)
        if status == 401:
            raise GitHubError(tr("GitHub rejected the configured token (401)."))
        if status == 404:
            raise GitHubError(tr("{what} was not found on GitHub (or it is private).", what=what))
        if status >= 400:
            raise GitHubError(tr("GitHub answered with an error ({status}) for {what}.", status=status, what=what))

    def get_json(self, path: str, what: str = ""):
        """GET on the API. Returns (data, offline): offline=True when served from cache after a failure."""
        url = path if path.startswith("http") else f"{self.api_url}/{path.lstrip('/')}"
        cache_file = self._cache_path("api", url)
        cached = self._read_cache(cache_file)
        headers = self._headers(url)
        if cached and cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        try:
            response = self._session().get(url, headers=headers, timeout=self.timeout)
            if response.status_code == 304 and cached:
                return cached["data"], False
            self._raise_for(response, what or url)
            data = response.json()
        except (GitHubError, ValueError) as exc:
            if cached and isinstance(exc, RateLimitError):
                return cached["data"], True
            raise
        except Exception as exc:  # noqa: BLE001 — network errors: fall back to the cache
            if cached:
                return cached["data"], True
            raise GitHubError(tr("Could not reach GitHub: {error}", error=exc)) from None
        if cache_file is not None:
            payload = {"etag": response.headers.get("ETag", ""), "saved": time.time(), "data": data}
            try:
                _atomic_write(cache_file, json.dumps(payload).encode("utf-8"))
            except OSError:
                pass
        return data, False

    # -- API -------------------------------------------------------------
    def repository(self, repo: str):
        """(Repository, offline)."""
        data, offline = self.get_json(f"repos/{repo}", what=repo)
        return parse_repository(data), offline

    def releases(self, repo: str, include_prerelease: bool = False, limit: int = 15):
        """Published releases, newest first: ([Release], offline). Drafts are never listed."""
        data, offline = self.get_json(f"repos/{repo}/releases?per_page={max(1, min(limit, 100))}", what=repo)
        releases = [parse_release(r) for r in data if isinstance(r, dict) and not r.get("draft")]
        if not include_prerelease:
            releases = [r for r in releases if not r.prerelease]
        releases.sort(key=lambda r: r.published.timestamp() if r.published else 0, reverse=True)
        return releases, offline

    # -- files -----------------------------------------------------------
    def download(self, asset: Asset, target: Path, on_progress=None, cancelled=None) -> Path:
        """Downloads `asset` to `target` via `<target>.part`, checking size and SHA-256.

        `on_progress(done_bytes, total_bytes_or_None)`; `cancelled()` -> True aborts
        with DownloadCancelled.
        """
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        if self.token and asset.api_url:
            url, accept = asset.api_url, "application/octet-stream"
        else:
            url, accept = asset.download_url, "application/octet-stream"
        digest = hashlib.sha256()
        done = 0
        try:
            response = self._session().get(url, headers=self._headers(url, accept), stream=True,
                                            timeout=(10, max(30, self.timeout * 3)))
            with response:
                self._raise_for(response, asset.name)
                total = asset.size or int(response.headers.get("Content-Length") or 0) or None
                with open(partial, "wb") as f:
                    for chunk in response.iter_content(_CHUNK):
                        if cancelled is not None and cancelled():
                            raise DownloadCancelled()
                        if not chunk:
                            continue
                        f.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        if on_progress is not None:
                            on_progress(done, total)
            if asset.size and done != asset.size:
                raise IntegrityError(tr("Incomplete download of {name}: {done} of {total} bytes.",
                                        name=asset.name, done=done, total=asset.size))
            if asset.digest and digest.hexdigest() != asset.digest:
                raise IntegrityError(tr("The SHA-256 of {name} does not match the one published on GitHub.",
                                        name=asset.name))
            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        return target

    def fetch_asset_icon(self, asset: Asset) -> Path | None:
        """Icon of an .exe asset, read with HTTP range requests and cached on disk.

        Only the PE headers and the resource section are downloaded. Returns
        None when the asset has no icon (that answer is cached too).
        """
        from . import peicon

        if self.cache_dir is None:
            raise GitHubError("no cache folder")
        folder = self.cache_dir / "icons"
        stem = f"asset-{asset.id or hashlib.sha1(asset.download_url.encode('utf-8')).hexdigest()}"
        for suffix in (".png", ".ico"):
            if (folder / (stem + suffix)).is_file():
                return folder / (stem + suffix)
        if (folder / (stem + ".none")).is_file():
            return None
        if self.token and asset.api_url:
            url = asset.api_url
        else:
            url = asset.download_url
        session = self._session()

        def read_at(offset: int, size: int) -> bytes:
            headers = self._headers(url, "application/octet-stream")
            headers["Range"] = f"bytes={offset}-{offset + size - 1}"
            response = session.get(url, headers=headers, stream=True, timeout=self.timeout)
            with response:
                if response.status_code != 206:      # no range support: never pull the whole file
                    self._raise_for(response, asset.name)
                    raise GitHubError(tr("{name} cannot be read in parts.", name=asset.name))
                data = bytearray()
                for chunk in response.iter_content(_CHUNK):
                    data.extend(chunk)
                    if len(data) >= size:
                        break
                return bytes(data[:size])

        try:
            data, kind = peicon.extract(read_at)
        except peicon.IconError:
            _atomic_write(folder / (stem + ".none"), b"")
            return None
        path = folder / f"{stem}.{kind}"
        _atomic_write(path, data)
        return path

    def fetch_file(self, url: str, max_bytes: int = 12 * 1024 * 1024, max_age: int = 6 * 3600) -> Path:
        """A small file (image) by URL, cached on disk and revalidated after `max_age` seconds."""
        suffix = Path(urlparse(url).path).suffix.lower()
        suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,5}", suffix or "") else ".bin"
        path = self._cache_path("files", url, suffix)
        if path is None:
            raise GitHubError("no cache folder")
        etag_file = path.with_name(path.name + ".etag")
        if path.is_file() and time.time() - path.stat().st_mtime < max_age:
            return path
        headers = self._headers(url, accept="*/*")
        if path.is_file() and etag_file.is_file():
            headers["If-None-Match"] = etag_file.read_text(encoding="utf-8").strip()
        try:
            response = self._session().get(url, headers=headers, timeout=self.timeout, stream=True)
            with response:
                if response.status_code == 304 and path.is_file():
                    os.utime(path)
                    return path
                self._raise_for(response, url)
                data = bytearray()
                for chunk in response.iter_content(_CHUNK):
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise GitHubError(tr("{name} exceeds {max} bytes", name=url, max=max_bytes))
            _atomic_write(path, bytes(data))
            if response.headers.get("ETag"):
                etag_file.write_text(response.headers["ETag"], encoding="utf-8")
        except Exception:
            if path.is_file():
                return path
            raise
        return path
