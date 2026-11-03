"""Leitura e validação do `launcher_config.json`.

Tudo o que é específico de um ambiente (servidor, aplicativos, opções que
viram variáveis de ambiente, downloads avulsos, login) vive no arquivo de
configuração. O código do launcher não conhece nenhum produto em particular.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE_NAME = "launcher_config.json"
EXAMPLE_CONFIG_FILE_NAME = "launcher_config.example.json"

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class ConfigError(ValueError):
    """Configuração ausente ou inválida."""


@dataclass(frozen=True)
class ServerConfig:
    protocol: str = "ftp"            # "ftp" | "ftps"
    host: str = ""
    port: int = 21
    user: str = "anonymous"
    password: str = ""
    password_enc: str = ""           # token V1 (ver launcher/crypto.py)
    secret: str = ""                 # base64 da chave usada em password_enc
    credentials_url: str = ""        # JSON remoto opcional com host/user/password
    encoding: str = "utf-8"
    timeout: int = 20


@dataclass(frozen=True)
class AuthConfig:
    type: str = "none"               # "none" | "http"
    url: str = ""
    title: str = "Entrar"
    user_label: str = "Usuário"
    success_contains: str = ""       # texto que precisa constar na resposta
    session_env_user: str = ""       # variável que recebe o usuário logado
    session_env_password: str = ""   # variável que recebe a senha da sessão
    timeout: int = 15

    @property
    def enabled(self) -> bool:
        return self.type != "none"


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
class CustomBuildsConfig:
    remote_subdir: str = "custom-builds"
    code_label: str = "Ticket"
    code_pattern: str = r"^\d{4,10}$"
    code_hint: str = "Informe o código fornecido pelo suporte."
    package_names: tuple = ("build.zip", "dist.zip")
    carry_over_files: tuple = ()     # copiados da instalação oficial


@dataclass(frozen=True)
class AppConfig:
    id: str
    name: str
    remote_dir: str
    package: str
    install_dir: str
    executable: str
    description: str = ""
    env: dict = field(default_factory=dict)
    extra_actions: tuple = ()
    options: tuple = ()
    custom_builds: CustomBuildsConfig | None = None


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
    remote_dir: str
    file_name: str = "Launcher.exe"


@dataclass(frozen=True)
class LauncherConfig:
    app_id: str
    app_name: str
    accent_color: str
    server: ServerConfig
    apps: tuple
    auth: AuthConfig = AuthConfig()
    support_url: str = ""
    downloads: tuple = ()
    self_update: SelfUpdateConfig | None = None
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
        raise ConfigError(f"{where}: campo obrigatório '{key}' ausente.")
    return value


def _str(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    return default if value is None else str(value)


def _parse_server(data: dict) -> ServerConfig:
    protocol = _str(data, "protocol", "ftp").lower()
    if protocol not in ("ftp", "ftps"):
        raise ConfigError("server.protocol deve ser 'ftp' ou 'ftps'.")
    if not data.get("host") and not data.get("credentials_url"):
        raise ConfigError("server: informe 'host' ou 'credentials_url'.")
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
        raise ConfigError("auth.type deve ser 'none' ou 'http'.")
    if kind == "http":
        _require(data, "url", "auth")
    session_env = data.get("session_env") or {}
    return AuthConfig(
        type=kind,
        url=_str(data, "url"),
        title=_str(data, "title", "Entrar"),
        user_label=_str(data, "user_label", "Usuário"),
        success_contains=_str(data, "success_contains"),
        session_env_user=_str(session_env, "user"),
        session_env_password=_str(session_env, "password"),
        timeout=int(data.get("timeout") or 15),
    )


def _parse_option(data: dict, where: str) -> AppOption:
    kind = _str(data, "type", "bool").lower()
    if kind not in ("bool", "text", "password"):
        raise ConfigError(f"{where}: type deve ser 'bool', 'text' ou 'password'.")
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


def _parse_custom_builds(data: dict | None) -> CustomBuildsConfig | None:
    if not data:
        return None
    pattern = _str(data, "code_pattern", CustomBuildsConfig.code_pattern)
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ConfigError(f"custom_builds.code_pattern inválido: {exc}") from None
    names = tuple(data.get("package_names") or CustomBuildsConfig.package_names)
    return CustomBuildsConfig(
        remote_subdir=_str(data, "remote_subdir", "custom-builds"),
        code_label=_str(data, "code_label", "Ticket"),
        code_pattern=pattern,
        code_hint=_str(data, "code_hint", CustomBuildsConfig.code_hint),
        package_names=names,
        carry_over_files=tuple(data.get("carry_over_files") or ()),
    )


def _parse_app(data: dict, index: int) -> AppConfig:
    where = f"apps[{index}]"
    app_id = _require(data, "id", where)
    if not _SLUG.match(app_id):
        raise ConfigError(f"{where}: id '{app_id}' deve conter apenas letras, números, '-', '_' ou '.'.")
    options = tuple(
        _parse_option(o, f"{where}.options[{i}]")
        for i, o in enumerate(data.get("options") or [])
    )
    keys = [o.key for o in options]
    if len(keys) != len(set(keys)):
        raise ConfigError(f"{where}: chaves de options repetidas.")
    actions = tuple(
        ExtraAction(
            label=_require(a, "label", f"{where}.extra_actions[{i}]"),
            executable=_require(a, "executable", f"{where}.extra_actions[{i}]"),
        )
        for i, a in enumerate(data.get("extra_actions") or [])
    )
    return AppConfig(
        id=app_id,
        name=_require(data, "name", where),
        remote_dir=_require(data, "remote_dir", where),
        package=_require(data, "package", where),
        install_dir=_str(data, "install_dir") or _require(data, "name", where),
        executable=_require(data, "executable", where),
        description=_str(data, "description"),
        env={str(k): str(v) for k, v in (data.get("env") or {}).items()},
        extra_actions=actions,
        options=options,
        custom_builds=_parse_custom_builds(data.get("custom_builds")),
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


def parse_config(data: dict, source: Path | None = None,
                 is_example: bool = False) -> LauncherConfig:
    if not isinstance(data, dict):
        raise ConfigError("O arquivo de configuração deve conter um objeto JSON.")

    apps = tuple(_parse_app(a, i) for i, a in enumerate(data.get("apps") or []))
    if not apps:
        raise ConfigError("Configure ao menos um aplicativo em 'apps'.")
    ids = [a.id for a in apps]
    if len(ids) != len(set(ids)):
        raise ConfigError("Há aplicativos com o mesmo 'id'.")

    accent = _str(data, "accent_color", "#7C5CFF")
    if not _HEX_COLOR.match(accent):
        raise ConfigError("accent_color deve estar no formato #RRGGBB.")

    app_name = _str(data, "app_name", "App Launcher")
    app_id = _str(data, "app_id") or re.sub(r"[^A-Za-z0-9]+", "", app_name) or "AppLauncher"

    self_update = None
    if data.get("self_update"):
        su = data["self_update"]
        self_update = SelfUpdateConfig(
            remote_dir=_require(su, "remote_dir", "self_update"),
            file_name=_str(su, "file_name", "Launcher.exe"),
        )

    return LauncherConfig(
        app_id=app_id,
        app_name=app_name,
        accent_color=accent,
        server=_parse_server(_require(data, "server", "config")),
        apps=apps,
        auth=_parse_auth(data.get("auth")),
        support_url=_str(data, "support_url"),
        downloads=tuple(
            _parse_download_tab(t, i) for i, t in enumerate(data.get("downloads") or [])
        ),
        self_update=self_update,
        source=source,
        is_example=is_example,
    )


def load_config(path: Path, is_example: bool = False) -> LauncherConfig:
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ConfigError(f"Não foi possível ler {path}: {exc}") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"JSON inválido em {Path(path).name} (linha {exc.lineno}, coluna {exc.colno}): {exc.msg}"
        ) from None
    return parse_config(data, source=Path(path), is_example=is_example)


def find_config(base_dir: Path, bundled_dir: Path, explicit: Path | None = None) -> LauncherConfig:
    """Localiza a configuração: --config > pasta do launcher > exemplo embutido."""
    if explicit is not None:
        return load_config(explicit)
    local = Path(base_dir) / CONFIG_FILE_NAME
    if local.is_file():
        return load_config(local)
    example = Path(bundled_dir) / EXAMPLE_CONFIG_FILE_NAME
    if example.is_file():
        return load_config(example, is_example=True)
    raise ConfigError(
        f"Arquivo '{CONFIG_FILE_NAME}' não encontrado em {base_dir}."
    )
