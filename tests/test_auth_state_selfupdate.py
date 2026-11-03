import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from launcher import auth, self_update
from launcher.config import AuthConfig
from launcher.state import StateStore


class ResolveStartupLoginTests(unittest.TestCase):
    def test_disabled_does_not_authenticate(self):
        fn = Mock()
        self.assertEqual(auth.resolve_startup_login(False, "ana", "pw", fn), (False, None))
        fn.assert_not_called()

    def test_missing_credentials_do_not_authenticate(self):
        fn = Mock()
        for user, pw in (("ana", ""), ("   ", "pw")):
            self.assertEqual(auth.resolve_startup_login(True, user, pw, fn), (False, None))
        fn.assert_not_called()

    def test_success(self):
        self.assertEqual(auth.resolve_startup_login(True, "ana", "pw", lambda u, p: True), (True, None))

    def test_invalid_credentials(self):
        self.assertEqual(auth.resolve_startup_login(True, "ana", "pw", lambda u, p: False),
                         (False, auth.AUTO_LOGIN_FAIL_MSG))

    def test_network_error_becomes_warning(self):
        fn = Mock(side_effect=ConnectionError("timeout"))
        skip, warning = auth.resolve_startup_login(True, "ana", "pw", fn)
        self.assertFalse(skip)
        self.assertIn("timeout", warning)

    def test_persist_only_when_enabled(self):
        save = Mock()
        self.assertTrue(auth.persist_session_if_auto_login(True, "ana", "pw", save))
        self.assertFalse(auth.persist_session_if_auto_login(False, "ana", "pw", save))
        self.assertFalse(auth.persist_session_if_auto_login(True, "ana", "", save))
        save.assert_called_once_with("ana", "pw")

    def test_session_env(self):
        cfg = AuthConfig(type="http", url="x", session_env_user="U", session_env_password="P")
        self.assertEqual(auth.session_env(cfg, " ana ", "pw"), {"U": "ana", "P": "pw"})
        self.assertEqual(auth.session_env(AuthConfig(), "ana", "pw"), {})


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "sub" / "state.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_persists_between_instances(self):
        store = StateStore(self.path)
        store.set_pref("auto_update", True)
        store.set_install_record("demo", "20260101000000", 42)
        again = StateStore(self.path)
        self.assertTrue(again.pref("auto_update"))
        self.assertEqual(again.install_record("demo"), ("20260101000000", 42))

    def test_secrets_are_not_stored_in_plain_text(self):
        store = StateStore(self.path)
        self.assertTrue(store.set_secret("pw", "super-secret"))
        self.assertNotIn("super-secret", self.path.read_text(encoding="utf-8"))
        self.assertEqual(StateStore(self.path).secret("pw"), "super-secret")

    def test_saved_login_round_trip(self):
        store = StateStore(self.path)
        auth.save_login(store, "ana", "pw")
        self.assertEqual(auth.load_saved_login(store), ("ana", "pw", True))
        auth.clear_login(store)
        self.assertEqual(auth.load_saved_login(store), ("", "", False))

    def test_corrupt_file_is_ignored(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{oops", encoding="utf-8")
        self.assertIsNone(StateStore(self.path).install_record("demo"))


class SelfUpdateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(Path(self._tmp.name) / "state.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_needs_update(self):
        self.assertFalse(self_update.needs_update(("m", 10), "m", 10, None))
        self.assertTrue(self_update.needs_update(("m", 10), "n", 10, None))
        self.assertFalse(self_update.needs_update(None, "m", 10, 10))
        self.assertTrue(self_update.needs_update(None, "m", 10, 9))

    def test_applied_marker_records_version_when_size_matches(self):
        argv, failed = self_update.consume_applied_args(
            ["app", self_update.MARKER, "20260101000000", "100", "--x"], self.store, exe_size=lambda: 100)
        self.assertEqual(argv, ["app", "--x"])
        self.assertFalse(failed)
        self.assertEqual(self.store.install_record(self_update.RECORD_KEY), ("20260101000000", 100))

    def test_applied_marker_flags_failed_swap(self):
        _, failed = self_update.consume_applied_args(
            ["app", self_update.MARKER, "20260101000000", "100"], self.store, exe_size=lambda: 90)
        self.assertTrue(failed)
        self.assertIsNone(self.store.install_record(self_update.RECORD_KEY))

    def test_swap_script_relaunches_with_marker(self):
        script = self_update.build_swap_script(Path("C:/a/L.exe"), Path("C:/a/L.new.exe"),
                                               Path("C:/a/L.old.exe"), 123, "20260101000000", 5)
        self.assertIn(f"{self_update.MARKER} 20260101000000 5", script)
        self.assertIn('set "PID=123"', script)


if __name__ == "__main__":
    unittest.main()
