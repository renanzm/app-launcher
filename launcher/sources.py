"""Where an application's versions come from: GitHub releases or an FTP package.

Both sources answer the same two questions — "what is the latest version?" and
"download it" — so the interface does not care where an app is published.
No Qt here; the interface runs these calls on worker threads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import github, remote
from .config import AppConfig
from .i18n import tr


@dataclass(frozen=True)
class Version:
    """A published version of an application."""
    key: str                          # identity compared with the installed record
    label: str                        # "v1.3.0" (GitHub) or the publication date (FTP)
    published: datetime | None = None
    size: int | None = None
    file_name: str = ""               # downloaded file; empty when there is nothing to install
    title: str = ""
    notes: str = ""                   # Markdown
    url: str = ""
    prerelease: bool = False
    payload: object = None            # github.Asset | remote.RemoteFile

    @property
    def installable(self) -> bool:
        return self.payload is not None


@dataclass(frozen=True)
class AppInfo:
    """What the source knows about an application right now."""
    latest: Version | None = None
    history: tuple = ()               # every release, newest first (GitHub)
    repository: github.Repository | None = None
    offline: bool = False             # answered from the cache because the network failed
    problem: str = ""                 # why there is nothing to install, when that is the case
    icon_asset: github.Asset | None = None   # .exe of the release whose icon represents the app


def ftp_key(mdtm: str | None, size: int | None) -> str:
    return f"ftp:{mdtm or ''}:{int(size or 0)}"


def github_key(tag: str, asset: github.Asset) -> str:
    return f"github:{tag}:{asset.id or asset.name}"


class GitHubAppSource:
    def __init__(self, app: AppConfig, client: github.GitHubClient):
        self.app = app
        self.client = client

    def check(self) -> AppInfo:
        repository, offline_repo = self.client.repository(self.app.github)
        releases, offline_releases = self.client.releases(self.app.github, self.app.prerelease)
        history = []
        for release in releases:
            asset = github.pick_asset(release.assets, self.app.asset)
            history.append(Version(
                key=github_key(release.tag, asset) if asset else f"github:{release.tag}:",
                label=release.tag,
                published=release.published,
                size=asset.size if asset else None,
                file_name=asset.name if asset else "",
                title=release.title,
                notes=release.notes,
                url=release.url,
                prerelease=release.prerelease,
                payload=asset,
            ))
        latest = next((v for v in history if v.installable), None)
        icon_asset = None
        for release in releases:
            icon_asset = github.pick_icon_asset(
                release.assets, self.app.executable,
                latest.payload if latest is not None and release.tag == latest.label else None)
            if icon_asset is not None:
                break
        problem = ""
        if not history:
            problem = tr("No release has been published yet.")
        elif latest is None:
            problem = (tr("No release has a file matching “{pattern}”.", pattern=self.app.asset)
                       if self.app.asset else tr("No release has a Windows file (.zip or .exe)."))
        return AppInfo(latest=latest, history=tuple(history), repository=repository,
                       offline=offline_repo or offline_releases, problem=problem, icon_asset=icon_asset)

    def download(self, version: Version, folder: Path, on_progress=None, cancelled=None) -> Path:
        return self.client.download(version.payload, Path(folder) / version.file_name,
                                    on_progress=on_progress, cancelled=cancelled)


class FtpAppSource:
    def __init__(self, app: AppConfig, server: remote.RemoteServer):
        self.app = app
        self.server = server

    def check(self) -> AppInfo:
        with self.server.connect() as ftp:
            ftp.cwd(self.app.remote_dir)
            rf = remote.stat(ftp, self.app.package)
        version = Version(
            key=ftp_key(rf.mdtm, rf.size),
            label=remote.format_mdtm(rf.mdtm),
            published=remote.mdtm_datetime(rf.mdtm),
            size=rf.size,
            file_name=rf.name,
            payload=rf,
        )
        return AppInfo(latest=version, history=(version,))

    def download(self, version: Version, folder: Path, on_progress=None, cancelled=None) -> Path:
        rf: remote.RemoteFile = version.payload
        with self.server.connect() as ftp:
            ftp.cwd(self.app.remote_dir)
            return remote.download(ftp, rf.name, Path(folder) / rf.name, rf.size,
                                   on_bytes=on_progress, cancelled=cancelled)


def make_source(app: AppConfig, client: github.GitHubClient | None, server: remote.RemoteServer | None):
    if app.source == "github":
        return GitHubAppSource(app, client)
    return FtpAppSource(app, server)


_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")


def markdown_images(markdown: str) -> list[str]:
    """http(s) image URLs in Markdown (``![alt](url)``) or HTML (``<img src>``) notes."""
    urls = re.findall(r"!\[[^\]]*\]\(\s*<?(https?://[^)\s>]+)", markdown or "")
    urls += re.findall(r"<img[^>]+src=[\"'](https?://[^\"']+)", markdown or "", flags=re.IGNORECASE)
    seen, out = set(), []
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


_LANGUAGE_WORDS = {
    "en": r"english|ingl[eê]s",
    "pt-BR": r"portugu[eê]s|portuguese|pt-br",
}


def _marker_language(line: str) -> str:
    """Language announced by a section marker line of bilingual notes ('' if not a marker).

    Markers: an anchor (``<a id="english">``), a heading made of the language name
    (``### Português``) or a line that starts with it in bold (``**English** · [Português](#pt)``).
    """
    text = line.strip()
    for code, words in _LANGUAGE_WORDS.items():
        if (re.match(rf"<a\s+(?:id|name)\s*=\s*[\"']?(?:{words})[\"'\s>]", text, re.IGNORECASE)
                or re.fullmatch(rf"#{{1,6}}\s*(?:{words})\s*#*", text, re.IGNORECASE)
                or re.match(rf"\*\*\s*(?:{words})\s*\*\*(?:\s*$|\s*[·|•-])", text, re.IGNORECASE)):
            return code
    return ""


def localized_notes(markdown: str, lang: str) -> str:
    """The part of bilingual release notes written in `lang` (English as the fallback).

    Notes with a single language — or without recognisable section markers — are
    returned unchanged. Text before the first marker (a title or a screenshot) is kept.
    """
    lines = (markdown or "").splitlines()
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current = ""
    for line in lines:
        code = _marker_language(line)
        if code:
            current = code
            sections.setdefault(code, [])
            continue
        (sections[current] if current else preamble).append(line)
    if len(sections) < 2:
        return markdown or ""
    chosen = sections.get(lang) or sections.get("en") or next(iter(sections.values()))
    return "\n".join(preamble + chosen).strip() + "\n"


def excerpt(markdown: str, limit: int = 180) -> str:
    """Plain-text summary of release notes: the first real paragraph, shortened."""
    text = re.sub(r"```.*?```", " ", markdown or "", flags=re.DOTALL)
    text = _MD_IMAGE.sub(" ", text)
    text = _HTML_TAG.sub(" ", text)
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        lines = []
        for line in block.splitlines():
            if re.match(r"^\s{0,3}#{1,6}\s", line):
                continue                                    # headings are not content
            line = re.sub(r"^\s{0,3}(>|[-*+]|\d+[.)])\s+", "", line)
            line = _MD_LINK.sub(r"\1", line)
            line = re.sub(r"[*_`~]+", "", line).strip()
            if line and not re.fullmatch(r"[-=|: ]+", line):
                lines.append(line)
        paragraph = " ".join(lines).strip()
        if paragraph:
            paragraphs.append(paragraph)
    chosen = next((p for p in paragraphs if len(p) >= 60), paragraphs[0] if paragraphs else "")
    chosen = re.sub(r"\s+", " ", chosen)
    if len(chosen) > limit:
        chosen = chosen[:limit].rsplit(" ", 1)[0].rstrip(",.;:—-") + "…"
    return chosen


def describe_record(record: dict | None) -> str:
    """Version label of an installed record ('' if unknown)."""
    if not record:
        return ""
    if record.get("version"):
        return str(record["version"])
    if record.get("mdtm"):
        return remote.format_mdtm(record["mdtm"])
    return ""
