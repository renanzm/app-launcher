import tempfile
import unittest
import zipfile
from pathlib import Path

from launcher import installer
from tests.helpers import make_config


def _make_zip(path: Path, entries: dict):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


class SafeExtractTests(unittest.TestCase):
    def test_extracts_nested_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "a.zip"
            _make_zip(z, {"app.exe": b"x", "lib/data.bin": b"y"})
            dest = Path(tmp) / "out"
            progress = []
            installer.safe_extract_zip(z, dest, on_progress=progress.append)
            self.assertEqual((dest / "lib" / "data.bin").read_bytes(), b"y")
            self.assertEqual(progress[-1], 100)

    def test_rejects_path_traversal(self):
        for evil in ("../evil.txt", "/abs.txt", "C:/win.txt", "a/../../evil.txt"):
            with self.subTest(evil=evil), tempfile.TemporaryDirectory() as tmp:
                z = Path(tmp) / "a.zip"
                _make_zip(z, {evil: b"x"})
                with self.assertRaises(ValueError):
                    installer.safe_extract_zip(z, Path(tmp) / "out")
                self.assertFalse((Path(tmp) / "evil.txt").exists())

    def test_clean_install_removes_old_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out"
            dest.mkdir()
            (dest / "old.txt").write_text("old")
            z = Path(tmp) / "a.zip"
            _make_zip(z, {"new.txt": b"n"})
            installer.install_package(z, dest, clean=True)
            self.assertFalse((dest / "old.txt").exists())
            self.assertTrue((dest / "new.txt").exists())

    def test_update_keeps_user_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out"
            dest.mkdir()
            (dest / "user.cfg").write_text("mine")
            z = Path(tmp) / "a.zip"
            _make_zip(z, {"app.exe": b"n"})
            installer.install_package(z, dest)
            self.assertEqual((dest / "user.cfg").read_text(), "mine")


class CustomBuildTests(unittest.TestCase):
    def setUp(self):
        self.app = make_config().apps[0]

    def test_pick_package_respects_priority(self):
        self.assertEqual(installer.pick_package_name(["dist.zip", "build.zip"], ("build.zip", "dist.zip")),
                         "build.zip")
        self.assertEqual(installer.pick_package_name(["dist.zip"], ("build.zip", "dist.zip")), "dist.zip")
        self.assertIsNone(installer.pick_package_name(["Build.zip"], ("build.zip",)))

    def test_code_validation(self):
        pattern = self.app.custom_builds.code_pattern
        self.assertTrue(installer.is_valid_code("12345", pattern))
        self.assertFalse(installer.is_valid_code("1234", pattern))
        self.assertFalse(installer.is_valid_code("12345a", pattern))
        self.assertFalse(installer.is_valid_code("", pattern))

    def test_list_builds_requires_executable_and_reads_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            good = installer.build_dir(base, self.app, "11111")
            good.mkdir()
            (good / self.app.executable).write_bytes(b"x")
            installer.write_build_meta(good, "11111", {"description": "fix"}, "20260101000000", 10)
            broken = installer.build_dir(base, self.app, "22222")
            broken.mkdir()
            builds = installer.list_builds(base, self.app)
            self.assertEqual([b["code"] for b in builds], ["11111"])
            self.assertEqual(builds[0]["description"], "fix")

    def test_carry_over_copies_only_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            official = Path(tmp) / "official"
            official.mkdir()
            (official / "settings.ini").write_text("user")
            target = Path(tmp) / "build"
            target.mkdir()
            (target / "settings.ini").write_text("default")
            copied = installer.carry_over_files(official, target, ["settings.ini", "missing.txt"])
            self.assertEqual(copied, ["settings.ini"])
            self.assertEqual((target / "settings.ini").read_text(), "user")

    def test_carry_over_without_official_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(installer.carry_over_files(None, Path(tmp), ["a"]), [])
            self.assertEqual(installer.carry_over_files(Path(tmp) / "nope", Path(tmp), ["a"]), [])


class LaunchEnvTests(unittest.TestCase):
    def setUp(self):
        self.app = make_config().apps[0]

    def test_options_become_env_vars(self):
        env = installer.build_launch_env(self.app, {"flag": True, "name": "abc"}, base_env={})
        self.assertEqual(env["DEMO_FLAG"], "1")
        self.assertEqual(env["DEMO_NAME"], "abc")

    def test_disabled_and_empty_options_remove_inherited_values(self):
        base = {"DEMO_FLAG": "1", "DEMO_NAME": "stale", "PATH": "x"}
        env = installer.build_launch_env(self.app, {"flag": False, "name": ""}, base_env=base)
        self.assertNotIn("DEMO_FLAG", env)
        self.assertNotIn("DEMO_NAME", env)
        self.assertEqual(env["PATH"], "x")
        self.assertEqual(base["DEMO_FLAG"], "1", "the base environment must not be modified")

    def test_defaults_apply_when_option_unset(self):
        env = installer.build_launch_env(self.app, {}, base_env={})
        self.assertEqual(env["DEMO_NAME"], "x")
        self.assertNotIn("DEMO_FLAG", env)

    def test_session_vars(self):
        env = installer.build_launch_env(self.app, {}, {"SESSION_USER": "ana", "SESSION_PW": ""},
                                         base_env={"SESSION_PW": "old"})
        self.assertEqual(env["SESSION_USER"], "ana")
        self.assertNotIn("SESSION_PW", env)


if __name__ == "__main__":
    unittest.main()
