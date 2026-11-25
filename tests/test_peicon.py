import struct
import sys
import tempfile
import unittest
from pathlib import Path

from launcher import github, peicon
from tests.test_github import FakeResponse, FakeSession, asset_json

# The Python interpreter is a Windows executable with an icon in its resources.
EXE = Path(sys.executable)


def range_server(body: bytes, calls: list):
    """Answers HTTP range requests from `body`, like GitHub's release download host."""
    def answer(headers):
        start, end = headers["Range"].removeprefix("bytes=").split("-")
        calls.append((int(start), int(end)))
        return FakeResponse(206, body=body[int(start):int(end) + 1])
    return answer


class ExtractTests(unittest.TestCase):
    def test_icon_of_an_executable(self):
        data, kind = peicon.extract_from_file(EXE)
        self.assertIn(kind, ("png", "ico"))
        if kind == "png":
            self.assertTrue(data.startswith(peicon.PNG_SIGNATURE))
        else:
            reserved, kind_, count = struct.unpack_from("<HHH", data, 0)
            self.assertEqual((reserved, kind_, count), (0, 1, 1))
            size, offset = struct.unpack_from("<II", data, 6 + 8)
            self.assertEqual(len(data), offset + size)

    def test_not_an_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = Path(tmp) / "a.exe"
            text.write_bytes(b"hello" * 100)
            with self.assertRaises(peicon.IconError):
                peicon.extract_from_file(text)
            truncated = Path(tmp) / "b.exe"
            truncated.write_bytes(EXE.read_bytes()[:600])
            with self.assertRaises(peicon.IconError):
                peicon.extract_from_file(truncated)


class AssetIconTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name)
        self.body = EXE.read_bytes()

    def tearDown(self):
        self._tmp.cleanup()

    def client(self, session):
        return github.GitHubClient(cache_dir=self.cache, session_factory=lambda: session)

    def test_reads_only_parts_and_caches(self):
        calls = []
        session = FakeSession([("github.com/dl", range_server(self.body, calls))])
        asset = github.parse_asset(asset_json("App.exe", size=len(self.body), id_=9))
        path = self.client(session).fetch_asset_icon(asset)
        self.assertIsNotNone(path)
        self.assertEqual(path.read_bytes(), peicon.extract_from_file(EXE)[0])
        self.assertLess(sum(end - start + 1 for start, end in calls), len(self.body))
        before = len(calls)
        self.assertEqual(self.client(session).fetch_asset_icon(asset), path)
        self.assertEqual(len(calls), before, "the second call is served from the cache")

    def test_no_icon_is_remembered(self):
        calls = []
        session = FakeSession([("github.com/dl", range_server(b"not an exe" * 50, calls))])
        asset = github.parse_asset(asset_json("tool.exe", id_=3))
        self.assertIsNone(self.client(session).fetch_asset_icon(asset))
        before = len(calls)
        self.assertIsNone(self.client(session).fetch_asset_icon(asset))
        self.assertEqual(len(calls), before)

    def test_server_without_range_support(self):
        session = FakeSession([("github.com/dl", FakeResponse(200, body=self.body))])
        asset = github.parse_asset(asset_json("App.exe", id_=4))
        with self.assertRaises(github.GitHubError):
            self.client(session).fetch_asset_icon(asset)

    def test_pick_icon_asset(self):
        assets = [github.parse_asset(asset_json(n, id_=i)) for i, n in
                  enumerate(("App-setup.exe", "App-win.zip", "Helper.exe", "App.exe"))]
        self.assertEqual(github.pick_icon_asset(assets, "bin/App.exe").name, "App.exe")
        self.assertEqual(github.pick_icon_asset(assets, "", installed=assets[3]).name, "App.exe")
        self.assertEqual(github.pick_icon_asset(assets[:3]).name, "Helper.exe")
        self.assertIsNone(github.pick_icon_asset(assets[:2]))


if __name__ == "__main__":
    unittest.main()
