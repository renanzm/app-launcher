"""Optional login before using the launcher.

With `auth.type = "http"`, the launcher sends `{"username", "password"}` as a
POST (JSON) to `auth.url`. Authentication is accepted when the response is
2xx and — if configured — contains the text `auth.success_contains`.
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
    """Function (user, password) -> bool for the configured login type."""
    if auth.type == "http":
        return lambda user, password: http_authenticate(auth, user, password)
    return lambda user, password: True


def resolve_startup_login(enabled, user, password, authenticate_fn):
    """Decides whether startup can skip the login screen.
    
    Returns `(skip_login, warning)`. `warning` is only filled in when automatic
    login was attempted and failed.
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
    """Variables that pass the authenticated session on to the launched application."""
    env = {}
    if auth.session_env_user:
        env[auth.session_env_user] = (user or "").strip()
    if auth.session_env_password:
        env[auth.session_env_password] = password or ""
    return env


# -- remembered credentials (encrypted with DPAPI in the StateStore) ---------

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
    """Saves the current session when automatic login is on."""
    user = (user or "").strip()
    if not enabled or not user or not password:
        return False
    save_fn(user, password)
    return True
