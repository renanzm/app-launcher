import ast
import string
import unittest
from pathlib import Path

from launcher import i18n, remote
from launcher.locales import pt_br

PACKAGE = Path(__file__).resolve().parent.parent / "launcher"


def _source_keys() -> set[str]:
    """Every literal passed to tr()/tr_noop() in the package."""
    keys = set()
    for path in PACKAGE.rglob("*.py"):
        if "locales" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("tr", "tr_noop")
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                keys.add(node.args[0].value)
    return keys


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


class CatalogTests(unittest.TestCase):
    def test_every_source_string_is_translated(self):
        missing = sorted(_source_keys() - set(pt_br.STRINGS))
        self.assertEqual(missing, [], "strings without a pt-BR translation")

    def test_no_stale_entries(self):
        stale = sorted(set(pt_br.STRINGS) - _source_keys())
        self.assertEqual(stale, [], "pt-BR entries no longer used by the code")

    def test_placeholders_match(self):
        for source, translated in pt_br.STRINGS.items():
            self.assertEqual(_fields(source), _fields(translated), source)


class LanguageTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_normalize(self):
        self.assertEqual(i18n.normalize("pt_BR"), "pt-BR")
        self.assertEqual(i18n.normalize("pt-br"), "pt-BR")
        self.assertEqual(i18n.normalize("pt"), "pt-BR")
        self.assertEqual(i18n.normalize("EN-us"), "en")
        self.assertEqual(i18n.normalize("auto"), "")
        self.assertEqual(i18n.normalize("xx"), "")

    def test_resolve_prefers_first_supported(self):
        self.assertEqual(i18n.resolve("", "pt-BR", "en"), "pt-BR")
        self.assertEqual(i18n.resolve(None, "auto", "en"), "en")

    def test_translate_and_fallback(self):
        self.assertEqual(i18n.tr("Install"), "Install")
        i18n.set_language("pt-BR")
        self.assertEqual(i18n.tr("Install"), "Instalar")
        self.assertEqual(i18n.tr("Build {code} installed.", code=7), "Build 7 instalada.")
        self.assertEqual(i18n.tr("Not in the catalogue {x}", x=1), "Not in the catalogue 1")

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(i18n.set_language("klingon"), "en")
        self.assertEqual(i18n.tr("Install"), "Install")

    def test_date_format_follows_language(self):
        self.assertRegex(remote.format_mdtm("20260102030405"), r"^2026-01-0[12] \d{2}:\d{2}$")
        i18n.set_language("pt-BR")
        self.assertRegex(remote.format_mdtm("20260102030405"), r"^0[12]/01/2026 \d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main()
