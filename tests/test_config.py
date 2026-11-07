import json
import tempfile
import unittest
from pathlib import Path

from launcher.config import (
    CONFIG_FILE_NAME, EXAMPLE_CONFIG_FILE_NAME, ConfigError, find_config, load_config,
    parse_config,
)
from tests.helpers import make_config

ROOT = Path(__file__).resolve().parent.parent


class ParseConfigTests(unittest.TestCase):
    def test_example_config_is_valid(self):
        config = load_config(ROOT / EXAMPLE_CONFIG_FILE_NAME)
        self.assertGreaterEqual(len(config.apps), 1)
        self.assertTrue(config.app("notes").custom_builds)

    def test_defaults(self):
        config = make_config()
        app = config.apps[0]
        self.assertEqual(app.install_dir, "Demo App")
        self.assertEqual(config.app_id, "TestLauncher")
        self.assertFalse(config.auth.enabled)
        self.assertEqual(config.server.protocol, "ftp")

    def test_requires_apps(self):
        with self.assertRaises(ConfigError):
            make_config(apps=[])

    def test_rejects_duplicate_app_ids(self):
        app = make_config().apps[0]
        raw = {"id": app.id, "name": "x", "remote_dir": "/", "package": "a.zip", "executable": "a.exe"}
        with self.assertRaises(ConfigError):
            make_config(apps=[raw, dict(raw)])

    def test_rejects_unsafe_app_id(self):
        with self.assertRaises(ConfigError):
            make_config(apps=[{"id": "../x", "name": "x", "remote_dir": "/",
                               "package": "a.zip", "executable": "a.exe"}])

    def test_rejects_invalid_accent(self):
        with self.assertRaises(ConfigError):
            make_config(accent_color="purple")

    def test_http_auth_requires_url(self):
        with self.assertRaises(ConfigError):
            make_config(auth={"type": "http"})

    def test_session_env_mapping(self):
        config = make_config(auth={"type": "http", "url": "https://x",
                                   "session_env": {"user": "U", "password": "P"}})
        self.assertEqual(config.auth.session_env_user, "U")
        self.assertEqual(config.auth.session_env_password, "P")

    def test_invalid_json_reports_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / CONFIG_FILE_NAME
            path.write_text("{ invalid", encoding="utf-8")
            with self.assertRaises(ConfigError) as ctx:
                load_config(path)
            self.assertIn("line 1", str(ctx.exception))


class FindConfigTests(unittest.TestCase):
    def _write(self, folder: Path, name: str, app_name: str):
        data = {"app_name": app_name, "server": {"host": "h"},
                "apps": [{"id": "a", "name": "A", "remote_dir": "/", "package": "a.zip",
                          "executable": "a.exe"}]}
        (folder / name).write_text(json.dumps(data), encoding="utf-8")

    def test_prefers_local_over_example(self):
        with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as bundle:
            self._write(Path(base), CONFIG_FILE_NAME, "Local")
            self._write(Path(bundle), EXAMPLE_CONFIG_FILE_NAME, "Example")
            config = find_config(Path(base), Path(bundle))
            self.assertEqual(config.app_name, "Local")
            self.assertFalse(config.is_example)

    def test_falls_back_to_example(self):
        with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as bundle:
            self._write(Path(bundle), EXAMPLE_CONFIG_FILE_NAME, "Example")
            config = find_config(Path(base), Path(bundle))
            self.assertTrue(config.is_example)

    def test_missing_everything(self):
        with tempfile.TemporaryDirectory() as base:
            with self.assertRaises(ConfigError):
                find_config(Path(base), Path(base))

    def test_parse_rejects_non_object(self):
        with self.assertRaises(ConfigError):
            parse_config([])


if __name__ == "__main__":
    unittest.main()
