"""Login opcional antes de usar o launcher.

Com `auth.type = "http"`, o launcher envia `{"username", "password"}` por
POST (JSON) para `auth.url`. A autenticação é aceita quando a resposta é
2xx e — se configurado — contém o texto `auth.success_contains`.
"""

from __future__ import annotations

from .config import AuthConfig
from .i18n import tr, tr_noop

AUTO_LOGIN_FAIL_MSG = tr_noop("Could not sign in automatically. Check your username and password.")

_USER_KEY = "login_user"
_PASSWORD_KEY = "login_password"


def http_authenticate(auth: AuthConfig, user: str, password: str) -> bool:
    import requests

    response = requests.post(
        auth.url, json={"username": user, "password": password}, timeout=auth.timeout
    )
    if response.status_code in (401, 403):
        return False
    response.raise_for_status()
    return not auth.success_contains or auth.success_contains in response.text


def make_authenticator(auth: AuthConfig):
    """Função (user, password) -> bool para o tipo de login configurado."""
    if auth.type == "http":
        return lambda user, password: http_authenticate(auth, user, password)
    return lambda user, password: True


def resolve_startup_login(enabled, user, password, authenticate_fn):
    """Decide se a abertura pode pular a tela de login.

    Retorna `(skip_login, warning)`. `warning` só vem preenchido quando o
    login automático foi tentado e falhou.
    """
    user = (user or "").strip()
    if not enabled or not user or not password:
        return False, None
    try:
        if authenticate_fn(user, password):
            return True, None
        return False, tr(AUTO_LOGIN_FAIL_MSG)
    except Exception as exc:
        return False, tr("Automatic sign-in failed:\n{error}", error=exc)


def session_env(auth: AuthConfig, user: str, password: str) -> dict:
    """Variáveis que repassam a sessão autenticada ao aplicativo iniciado."""
    env = {}
    if auth.session_env_user:
        env[auth.session_env_user] = (user or "").strip()
    if auth.session_env_password:
        env[auth.session_env_password] = password or ""
    return env


# -- credenciais lembradas (cifradas com DPAPI no StateStore) ---------------

def load_saved_login(store):
    """(user, password, remember)."""
    user = store.get("login", "user", "")
    password = store.secret(_PASSWORD_KEY) or ""
    remember = bool(store.get("login", "remember", False))
    return (user, password, True) if remember and user else ("", "", False)


def save_login(store, user: str, password: str):
    store.set("login", "user", user)
    store.set("login", "remember", True)
    store.set_secret(_PASSWORD_KEY, password)


def clear_login(store):
    store.set("login", "remember", False)
    store.delete("login", "user")
    store.delete_secret(_PASSWORD_KEY)


def persist_session_if_auto_login(enabled, user, password, save_fn):
    """Grava a sessão atual quando o login automático está ligado."""
    user = (user or "").strip()
    if not enabled or not user or not password:
        return False
    save_fn(user, password)
    return True
