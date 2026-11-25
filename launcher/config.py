"""Reading and validating `launcher_config.json`.

Everything environment-specific (where applications come from, options that
become environment variables, standalone downloads, login) lives in the
configuration file. The launcher code knows no particular product.

An application comes from one of two sources:

- **GitHub** (`"github": "owner/repo"`): the latest release of the repository,
  using the asset that matches `asset` (a `.zip` or an `.exe`);
- **FTP/FTPS** (`"remote_dir"` + `"package"`): a package on the `server`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .i18n import tr

CONFIG_FILE_NAME = "launcher_config.json"
EXAMPLE_CONFIG_FILE_NAME = "launcher_config.example.json"

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Text shown to the user: a plain string or {"en": "...", "pt-BR": "..."}.
Text = str | dict


class ConfigError(ValueError):
    """Missing or invalid configuration."""


@dataclass(frozen=True)
class ServerConfig:
    protocol: str = "ftp"            # "ftp" | "ftps"
    host: str = ""
    port: int = 21
    user: str = "anonymous"
    password: str = ""
    password_enc: str = ""           # V1 token (see launcher/crypto.py)
    secret: str = ""                 # base64 of the key used for password_enc
    credentials_url: str = ""        # optional remote JSON with host/user/password
    encoding: str = "utf-8"
    timeout: int = 20


@dataclass(frozen=True)
class AuthConfig:
    type: str = "none"               # "none" | "http"
    url: str = ""
    title: str = ""                  # empty -> translated default ("Sign in")
    user_label: str = ""             # empty -> translated default ("Username")
    success_contains: str = ""       # text the response must contain
    session_env_user: str = ""       # variable that receives the signed-in user
    session_env_password: str = ""   # variable that receives the session password
    timeout: int = 15

    @property
    def enabled(self) -> bool:
        return self.type != "none"


@dataclass(frozen=True)
class GitHubSettings:
    token: str = ""                  # optional: private repositories / higher rate limit
    timeout: int = 20


@dataclass(frozen=True)
class AppOption:
    key: str
    label: str
    type: str = "bool"               # "bool" | "text" | "password"
    env: str = ""
    default: object = None
    description: str = ""


@dataclass(frozen=True)
class ExtraAction:
    label: str
    executable: str


@dataclass(frozen=True)
class AppLink:
    label: Text
    url: str


@dataclass(frozen=True)
class AppConfig:
    id: str
    name: str
    install_dir: str
    executable: str = ""             # may be empty for GitHub apps (detected on install)
    # FTP source
    remote_dir: str = ""
    package: str = ""
    # GitHub source
    github: str = ""                 # "owner/repo"
    asset: str = ""                  # glob of the release asset; empty = automatic
    prerelease: bool = False         # also offer pre-releases
    # presentation
    description: Text = ""
    tagline: Text = ""
    accent_color: str = ""           # empty = the launcher accent
    banner: Text = ""                # image (URL or path) that fills the header
    screenshot: Text = ""            # image (URL or path) shown framed in the header
    icon: str = ""                   # image (URL or path) for the library
    links: tuple = ()
    env: dict = field(default_factory=dict)
    extra_actions: tuple = ()
    options: tuple = ()

    @property
    def source(self) -> str:
        return "github" if self.github else "ftp"


@dataclass(frozen=True)
class DownloadExtraFile:
    name: str
    remote_dir: str
    badge: str = ""


@dataclass(frozen=True)
class DownloadTab:
    label: str
    remote_dir: str
    destination: str
    extra_files: tuple = ()


@dataclass(frozen=True)
class SelfUpdateConfig:
    remote_dir: str = ""             # FTP: folder of the published .exe
    file_name: str = "Launcher.exe"
    github: str = ""                 # GitHub: "owner/repo" whose releases carry the .exe

    @property
    def source(self) -> str:
        return "github" if self.github else "ftp"


@dataclass(frozen=True)
class LauncherConfig:
    app_id: str
    app_name: str
    accent_color: str
    server: ServerConfig | None
    apps: tuple
    auth: AuthConfig = AuthConfig()
    github: GitHubSettings = GitHubSettings()
    support_url: str = ""
    downloads: tuple = ()
    self_update: SelfUpdateConfig | None = None
    language: str = ""              # "" / "auto" follows the system
    install_root: str = ""          # folder for installed apps; "" = launcher folder
    source: Path | None = None
    is_example: bool = False

    def app(self, app_id: str) -> AppConfig | None:
        return next((a for a in self.apps if a.id == app_id), None)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _require(data: dict, key: str, where: str):
    value = data.get(key)
    if value in (None, ""):
        raise ConfigError(tr("{where}: required field '{key}' is missing.", where=where, key=key))
    return value


def _str(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    return default if value is None else str(value)


def _text(data: dict, key: str, where: str) -> Text:
    """A user-facing text: a string or a {language: text} object."""
    value = data.get(key)
    if value is None:
        return ""
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        raise ConfigError(tr("{where}: '{key}' must be a text or an object of translations.",
                             where=where, key=key))
    return str(value)


def _color(data: dict, key: str, where: str) -> str:
    value = _str(data, key)
    if value and not _HEX_COLOR.match(value):
        raise ConfigError(tr("{where}: {key} must be in the #RRGGBB format.", where=where, key=key))
    return value


def _repo(value: str, where: str) -> str:
    repo = value.strip().strip("/")
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if repo.lower().startswith(prefix):
            repo = repo[len(prefix):].strip("/")
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not _REPO.match(repo):
        raise ConfigError(tr("{where}: github must be in the 'owner/repository' format.", where=where))
    return repo


def _relative_path(value: str, where: str, key: str) -> str:
    """A path that must stay inside the install folder."""
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", value):
        raise ConfigError(tr("{where}: {key} must be a path inside the install folder.",
                             where=where, key=key))
    return value


def _parse_server(data: dict) -> ServerConfig:
    protocol = _str(data, "protocol", "ftp").lower()
    if protocol not in ("ftp", "ftps"):
        raise ConfigError(tr("server.protocol must be 'ftp' or 'ftps'."))
    if not data.get("host") and not data.get("credentials_url"):
        raise ConfigError(tr("server: set 'host' or 'credentials_url'."))
    return ServerConfig(
        protocol=protocol,
        host=_str(data, "host"),
        port=int(data.get("port") or 21),
        user=_str(data, "user", "anonymous"),
        password=_str(data, "password"),
        password_enc=_str(data, "password_enc"),
        secret=_str(data, "secret"),
        credentials_url=_str(data, "credentials_url"),
        encoding=_str(data, "encoding", "utf-8"),
        timeout=int(data.get("timeout") or 20),
    )


def _parse_auth(data: dict | None) -> AuthConfig:
    if not data:
        return AuthConfig()
    kind = _str(data, "type", "none").lower()
    if kind not in ("none", "http"):
        raise ConfigError(tr("auth.type must be 'none' or 'http'."))
    if kind == "http":
        _require(data, "url", "auth")
    session_env = data.get("session_env") or {}
    return AuthConfig(
        type=kind,
        url=_str(data, "url"),
        title=_str(data, "title"),
        user_label=_str(data, "user_label"),
        success_contains=_str(data, "success_contains"),
        session_env_user=_str(session_env, "user"),
        session_env_password=_str(session_env, "password"),
        timeout=int(data.get("timeout") or 15),
    )


def _parse_option(data: dict, where: str) -> AppOption:
    kind = _str(data, "type", "bool").lower()
    if kind not in ("bool", "text", "password"):
        raise ConfigError(tr("{where}: type must be 'bool', 'text' or 'password'.", where=where))
    default = data.get("default")
    if default is None:
        default = False if kind == "bool" else ""
    return AppOption(
        key=_require(data, "key", where),
        label=_require(data, "label", where),
        type=kind,
        env=_str(data, "env"),
        default=default,
        description=_str(data, "description"),
    )


def _parse_app(data: dict, index: int) -> AppConfig:
    where = f"apps[{index}]"
    if not isinstance(data, dict):
        raise ConfigError(tr("{where} must be an object.", where=where))
    app_id = _require(data, "id", where)
    if not _SLUG.match(app_id):
        raise ConfigError(tr("{where}: id '{id}' may only contain letters, digits, '-', '_' or '.'.",
                             where=where, id=app_id))
    github = _repo(_str(data, "github"), where) if data.get("github") else ""
    if github:
        remote_dir = package = ""
        executable = _str(data, "executable")
    else:
        remote_dir = _require(data, "remote_dir", where)
        package = _require(data, "package", where)
        executable = _require(data, "executable", where)
    if executable:
        _relative_path(executable, where, "executable")

    options = tuple(
        _parse_option(o, f"{where}.options[{i}]")
        for i, o in enumerate(data.get("options") or [])
    )
    keys = [o.key for o in options]
    if len(keys) != len(set(keys)):
        raise ConfigError(tr("{where}: duplicate option keys.", where=where))
    actions = tuple(
        ExtraAction(
            label=_require(a, "label", f"{where}.extra_actions[{i}]"),
            executable=_relative_path(_require(a, "executable", f"{where}.extra_actions[{i}]"),
                                      f"{where}.extra_actions[{i}]", "executable"),
        )
        for i, a in enumerate(data.get("extra_actions") or [])
    )
    links = []
    for i, link in enumerate(data.get("links") or []):
        link_where = f"{where}.links[{i}]"
        _require(link, "label", link_where)
        links.append(AppLink(label=_text(link, "label", link_where), url=_require(link, "url", link_where)))

    name = _require(data, "name", where)
    return AppConfig(
        id=app_id,
        name=name,
        install_dir=_relative_path(_str(data, "install_dir") or name, where, "install_dir"),
        executable=executable,
        remote_dir=remote_dir,
        package=package,
        github=github,
        asset=_str(data, "asset"),
        prerelease=bool(data.get("prerelease", False)),
        description=_text(data, "description", where),
        tagline=_text(data, "tagline", where),
        accent_color=_color(data, "accent_color", where),
        banner=_text(data, "banner", where),
        screenshot=_text(data, "screenshot", where),
        icon=_str(data, "icon"),
        links=tuple(links),
        env={str(k): str(v) for k, v in (data.get("env") or {}).items()},
        extra_actions=actions,
        options=options,
    )


def _parse_download_tab(data: dict, index: int) -> DownloadTab:
    where = f"downloads[{index}]"
    extras = tuple(
        DownloadExtraFile(
            name=_require(e, "name", f"{where}.extra_files[{i}]"),
            remote_dir=_require(e, "remote_dir", f"{where}.extra_files[{i}]"),
            badge=_str(e, "badge"),
        )
        for i, e in enumerate(data.get("extra_files") or [])
    )
    label = _require(data, "label", where)
    return DownloadTab(
        label=label,
        remote_dir=_require(data, "remote_dir", where),
        destination=_str(data, "destination") or label,
        extra_files=extras,
    )


def _parse_self_update(data: dict) -> SelfUpdateConfig:
    if data.get("github"):
        return SelfUpdateConfig(github=_repo(_str(data, "github"), "self_update"),
                                file_name=_str(data, "file_name", "Launcher.exe"))
    return SelfUpdateConfig(
        remote_dir=_require(data, "remote_dir", "self_update"),
        file_name=_str(data, "file_name", "Launcher.exe"),
    )


def parse_config(data: dict, source: Path | None = None,
                 is_example: bool = False) -> LauncherConfig:
    if not isinstance(data, dict):
        raise ConfigError(tr("The configuration file must contain a JSON object."))

    apps = tuple(_parse_app(a, i) for i, a in enumerate(data.get("apps") or []))
    if not apps:
        raise ConfigError(tr("Configure at least one application in 'apps'."))
    ids = [a.id for a in apps]
    if len(ids) != len(set(ids)):
        raise ConfigError(tr("Some applications share the same 'id'."))

    accent = _str(data, "accent_color", "#7C5CFF")
    if not _HEX_COLOR.match(accent):
        raise ConfigError(tr("accent_color must be in the #RRGGBB format."))

    app_name = _str(data, "app_name", "App Launcher")
    app_id = _str(data, "app_id") or re.sub(r"[^A-Za-z0-9]+", "", app_name) or "AppLauncher"

    self_update = _parse_self_update(data["self_update"]) if data.get("self_update") else None
    downloads = tuple(
        _parse_download_tab(t, i) for i, t in enumerate(data.get("downloads") or [])
    )

    # The FTP server is only required when something is served by it.
    needs_server = (any(a.source == "ftp" for a in apps) or bool(downloads)
                    or (self_update is not None and self_update.source == "ftp"))
    server = None
    if data.get("server") or needs_server:
        server = _parse_server(_require(data, "server", "config"))

    github = data.get("github") or {}
    if not isinstance(github, dict):
        raise ConfigError(tr("'github' must be an object."))

    return LauncherConfig(
        app_id=app_id,
        app_name=app_name,
        accent_color=accent,
        server=server,
        apps=apps,
        auth=_parse_auth(data.get("auth")),
        github=GitHubSettings(token=_str(github, "token"), timeout=int(github.get("timeout") or 20)),
        support_url=_str(data, "support_url"),
        downloads=downloads,
        self_update=self_update,
        language=_str(data, "language"),
        install_root=_str(data, "install_root"),
        source=source,
        is_example=is_example,
    )


def load_config(path: Path, is_example: bool = False) -> LauncherConfig:
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ConfigError(tr("Could not read {path}: {error}", path=path, error=exc)) from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            tr("Invalid JSON in {name} (line {line}, column {column}): {error}",
               name=Path(path).name, line=exc.lineno, column=exc.colno, error=exc.msg)
        ) from None
    return parse_config(data, source=Path(path), is_example=is_example)


def find_config(base_dir: Path, bundled_dir: Path, explicit: Path | None = None) -> LauncherConfig:
    """Locates the configuration: --config > launcher folder > bundled example."""
    if explicit is not None:
        return load_config(explicit)
    local = Path(base_dir) / CONFIG_FILE_NAME
    if local.is_file():
        return load_config(local)
    example = Path(bundled_dir) / EXAMPLE_CONFIG_FILE_NAME
    if example.is_file():
        return load_config(example, is_example=True)
    raise ConfigError(tr("File '{name}' not found in {folder}.", name=CONFIG_FILE_NAME, folder=base_dir))
