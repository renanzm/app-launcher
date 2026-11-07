"""Tests against a real FTP server (pyftpdlib) running in a thread."""

import hashlib
import logging
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from launcher import remote
from launcher.config import ServerConfig

try:
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
except ImportError:  # pragma: no cover
    FTPServer = None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipIf(FTPServer is None, "pyftpdlib não instalado (requirements-dev.txt)")
class RemoteFtpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.getLogger("pyftpdlib").setLevel(logging.WARNING)
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name) / "srv"
        (cls.root / "apps" / "sub").mkdir(parents=True)
        cls.payload = b"x" * 200_000
        (cls.root / "apps" / "pkg.zip").write_bytes(cls.payload)
        (cls.root / "apps" / "pkg.zip.sha256").write_text(
            hashlib.sha256(cls.payload).hexdigest() + "  pkg.zip\n")
        (cls.root / "apps" / "bad.zip").write_bytes(b"conteudo")
        (cls.root / "apps" / "bad.zip.sha256").write_text("0" * 64)
        (cls.root / "apps" / "Ação.txt").write_text("acentos", encoding="utf-8")

        authorizer = DummyAuthorizer()
        authorizer.add_user("u", "p", str(cls.root), perm="elr")
        handler = type("Handler", (FTPHandler,), {"authorizer": authorizer})
        port = _free_port()
        cls.server = FTPServer(("127.0.0.1", port), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"timeout": 0.2},
                                      daemon=True)
        cls.thread.start()
        cls.remote = remote.RemoteServer(ServerConfig(host="127.0.0.1", port=port, user="u",
                                                      password="p", timeout=5))

    @classmethod
    def tearDownClass(cls):
        cls.server.close_all()
        cls._tmp.cleanup()

    def test_stat_and_download_with_hash(self):
        with tempfile.TemporaryDirectory() as tmp, self.remote.connect() as ftp:
            ftp.cwd("/apps")
            info = remote.stat(ftp, "pkg.zip")
            self.assertEqual(info.size, len(self.payload))
            self.assertRegex(info.mdtm, r"^\d{14}")
            progress = []
            target = remote.download(ftp, "pkg.zip", Path(tmp) / "pkg.zip", info.size,
                                     on_progress=progress.append)
            self.assertEqual(target.read_bytes(), self.payload)
            self.assertEqual(progress[-1], 100)
            self.assertFalse((Path(tmp) / "pkg.zip.part").exists())

    def test_hash_mismatch_discards_file(self):
        with tempfile.TemporaryDirectory() as tmp, self.remote.connect() as ftp:
            ftp.cwd("/apps")
            with self.assertRaises(remote.IntegrityError):
                remote.download(ftp, "bad.zip", Path(tmp) / "bad.zip", 8)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_size_mismatch_discards_file(self):
        with tempfile.TemporaryDirectory() as tmp, self.remote.connect() as ftp:
            ftp.cwd("/apps")
            with self.assertRaises(remote.IntegrityError):
                remote.download(ftp, "pkg.zip", Path(tmp) / "pkg.zip", 5)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_list_files_skips_directories_and_handles_accents(self):
        with self.remote.connect() as ftp:
            ftp.cwd("/apps")
            names = {f.name for f in remote.list_files(ftp)}
        self.assertIn("pkg.zip", names)
        self.assertIn("Ação.txt", names)
        self.assertNotIn("sub", names)

    def test_file_info_from_other_directory_restores_cwd(self):
        with self.remote.connect() as ftp:
            ftp.cwd("/apps/sub")
            info = remote.file_info(ftp, "/apps", "PKG.ZIP")
            self.assertEqual(info.size, len(self.payload))
            self.assertEqual(ftp.pwd(), "/apps/sub")
            missing = remote.file_info(ftp, "/nope", "x.zip")
            self.assertIsNone(missing.size)

    def test_try_cwd_and_read_text(self):
        with self.remote.connect() as ftp:
            self.assertFalse(remote.try_cwd(ftp, "/does-not-exist"))
            self.assertTrue(remote.try_cwd(ftp, "/apps"))
            self.assertIsNone(remote.read_text(ftp, "missing.json"))
            self.assertEqual(remote.read_text(ftp, "Ação.txt"), "acentos")


class FormatTests(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(remote.format_size(None), "—")
        self.assertEqual(remote.format_size(512), "512 B")
        self.assertEqual(remote.format_size(2048), "2.0 KB")

    def test_format_mdtm_handles_fraction_and_garbage(self):
        self.assertEqual(remote.format_mdtm(None), "—")
        self.assertRegex(remote.format_mdtm("20260102030405.123"), r"^2026-01-0[12] \d{2}:\d{2}$")
        self.assertEqual(remote.format_mdtm("bogus"), "bogus")


if __name__ == "__main__":
    unittest.main()
