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

    def test_update_keeps_user_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out"
            dest.mkdir()
            (dest / "user.cfg").write_text("mine")
            z = Path(tmp) / "a.zip"
            _make_zip(z, {"app.exe": b"n"})
            installer.install_package(z, dest)
            self.assertEqual((dest / "user.cfg").read_text(), "mine")


class InstallDownloadTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def app(self, **extra):
        return make_config(apps=[{"id": "x", "name": "Sound Mod", "github": "o/sound-mod", **extra}]).apps[0]

    def test_common_root(self):
        self.assertEqual(installer.common_root(["App-v1/", "App-v1/app.exe", "App-v1/lib/x.dll"]), "App-v1")
        self.assertEqual(installer.common_root(["app.exe", "lib/x.dll"]), "")
        self.assertEqual(installer.common_root(["A/a.exe", "B/b.exe"]), "")
        self.assertEqual(installer.common_root(["App/app.exe"], executable="App/app.exe"), "")

    def test_zip_with_root_folder_is_flattened_and_exe_detected(self):
        z = self.tmp / "pkg.zip"
        _make_zip(z, {"SoundMod-v1/SoundMod.exe": b"x" * 2048, "SoundMod-v1/unins000.exe": b"u",
                      "SoundMod-v1/docs/manual.html": b"m"})
        dest = self.tmp / "out"
        exe = installer.install_download(z, dest, self.app())
        self.assertEqual(exe, "SoundMod.exe")
        self.assertTrue((dest / "docs" / "manual.html").is_file())
        self.assertFalse((dest / "SoundMod-v1").exists())

    def test_single_exe_is_moved_into_place(self):
        exe = self.tmp / "tool-v2.exe"
        exe.write_bytes(b"MZ")
        dest = self.tmp / "out"
        self.assertEqual(installer.install_download(exe, dest, self.app()), "tool-v2.exe")
        self.assertEqual((dest / "tool-v2.exe").read_bytes(), b"MZ")
        exe.write_bytes(b"MZ2")
        self.assertEqual(installer.install_download(exe, dest, self.app(executable="Tool.exe")), "Tool.exe")
        self.assertEqual((dest / "Tool.exe").read_bytes(), b"MZ2")

    def test_unsupported_file(self):
        msi = self.tmp / "setup.msi"
        msi.write_bytes(b"x")
        with self.assertRaises(ValueError):
            installer.install_download(msi, self.tmp / "out", self.app())

    def test_resolve_root(self):
        base = Path("C:/Launcher")
        self.assertEqual(installer.resolve_root(base, ""), base)
        self.assertEqual(installer.resolve_root(base, "Apps"), base / "Apps")
        self.assertEqual(installer.resolve_root(base, "D:/Games"), Path("D:/Games"))


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
