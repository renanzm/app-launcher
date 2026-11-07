"""Internationalisation: English is the source language, other catalogues translate it.

Every user-facing string in the code is written in English and passed through
`tr()`. A catalogue (`launcher/locales/<code>.py`) maps the English text to its
translation; a missing entry falls back to the English text, so a partial
catalogue never breaks the interface.

    tr("Install")                         -> "Instalar" (pt-BR)
    tr("Build {code} installed.", code=1) -> "Build 1 instalada." (pt-BR)
"""

from __future__ import annotations

import importlib
import locale
import os
import sys

DEFAULT_LANGUAGE = "en"
# code -> name shown in the language selector (always in its own language)
LANGUAGES = {"en": "English", "pt-BR": "Português (Brasil)"}
AUTO = "auto"

_language = DEFAULT_LANGUAGE
_catalog: dict[str, str] = {}


def normalize(code: str | None) -> str:
    """Maps 'pt', 'pt_BR', 'pt-br'… to a supported code; unknown values -> ''."""
    text = (code or "").strip().replace("_", "-").lower()
    if not text or text == AUTO:
        return ""
    for supported in LANGUAGES:
        if text == supported.lower():
            return supported
    base = text.split("-")[0]
    for supported in LANGUAGES:
        if supported.lower().split("-")[0] == base:
            return supported
    return ""


def system_language() -> str:
    """Language of the operating system, restricted to the supported ones."""
    names = []
    if sys.platform == "win32":
        try:
            import ctypes
            buffer = ctypes.create_unicode_buffer(85)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
                names.append(buffer.value)
        except Exception:  # noqa: BLE001 — falls through to the generic lookup
            pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(var):
            names.append(os.environ[var].split(".")[0])
    try:
        names.append(locale.getlocale()[0] or "")
    except (ValueError, TypeError):
        pass
    for name in names:
        found = normalize(name)
        if found:
            return found
    return DEFAULT_LANGUAGE


def resolve(*preferences: str | None) -> str:
    """First supported code among `preferences`; 'auto'/empty means the system language."""
    for pref in preferences:
        found = normalize(pref)
        if found:
            return found
    return system_language()


def set_language(code: str | None) -> str:
    """Activates a language (falls back to English) and returns the code in use."""
    global _language, _catalog
    code = normalize(code) or DEFAULT_LANGUAGE
    _catalog = {}
    if code != DEFAULT_LANGUAGE:
        module = importlib.import_module(f"launcher.locales.{code.lower().replace('-', '_')}")
        _catalog = dict(module.STRINGS)
    _language = code
    return code


def language() -> str:
    return _language


def tr(text: str, **values) -> str:
    """Translates `text`; `{name}` placeholders are filled from `values`."""
    out = _catalog.get(text, text)
    return out.format(**values) if values else out


def tr_noop(text: str) -> str:
    """Marks a string for the catalogue without translating it yet."""
    return text
