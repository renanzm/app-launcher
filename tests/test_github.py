import hashlib
import tempfile
import unittest
from pathlib import Path

from launcher import github, sources
from launcher.config import parse_config


class FakeResponse:
    def __init__(self, status=200, data=None, body=b"", headers=None):
        self.status_code = status
        self._data = data
        self._body = body
        self.headers = headers or {}

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data

    def iter_content(self, size):
        for i in range(0, len(self._body), 4):
            yield self._body[i:i + 4]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSession:
    """Answers GETs from a list of (url fragment, response | exception)."""

    def __init__(self, routes):
        self.routes = routes
        self.headers = {}
        self.calls = []

    def get(self, url, headers=None, **kwargs):
        self.calls.append((url, dict(headers or {})))
        for fragment, answer in self.routes:
            if fragment in url:
                if isinstance(answer, Exception):
                    raise answer
                return answer(headers or {}) if callable(answer) else answer
        return FakeResponse(404)


def release_json(tag="v1.2.0", assets=(), prerelease=False, draft=False, body="Notes"):
    return {"tag_name": tag, "name": f"App {tag}", "body": body, "html_url": f"https://x/{tag}",
            "published_at": "2026-11-20T10:00:00Z", "prerelease": prerelease, "draft": draft,
            "assets": list(assets)}


def asset_json(name, size=10, digest=None, id_=1):
    return {"id": id_, "name": name, "size": size, "url": f"https://api.github.com/assets/{id_}",
            "browser_download_url": f"https://github.com/dl/{name}", "updated_at": "2026-11-20T10:00:00Z",
            "digest": digest, "state": "uploaded"}


class ParsingTests(unittest.TestCase):
    def test_asset_digest_and_kind(self):
        digest = "a" * 64
        asset = github.parse_asset(asset_json("App.EXE", digest=f"sha256:{digest}"))
        self.assertEqual(asset.digest, digest)
        self.assertEqual(asset.kind, "exe")
        self.assertIsNone(github.parse_asset(asset_json("x.zip", digest="md5:abc")).digest)
        self.assertEqual(github.parse_asset(asset_json("notes.txt")).kind, "")

    def test_release(self):
        rel = github.parse_release(release_json(assets=[asset_json("a.zip")]))
        self.assertEqual(rel.tag, "v1.2.0")
        self.assertEqual(rel.title, "App v1.2.0")
        self.assertEqual(rel.published.year, 2026)
        self.assertEqual(len(rel.assets), 1)


class PickAssetTests(unittest.TestCase):
    def assets(self, *names):
        return [github.parse_asset(asset_json(n, id_=i)) for i, n in enumerate(names)]

    def test_pattern_is_case_insensitive_glob(self):
        found = github.pick_asset(self.assets("App-v1-windows-x64.zip", "App.exe"), "app-*-WINDOWS-x64.zip")
        self.assertEqual(found.name, "App-v1-windows-x64.zip")
        self.assertIsNone(github.pick_asset(self.assets("App.exe"), "*.zip"))

    def test_automatic_prefers_portable_windows_build(self):
        found = github.pick_asset(self.assets("App-linux.zip", "App-setup.exe", "App-win-x64.zip",
                                              "checksums.txt"))
        self.assertEqual(found.name, "App-win-x64.zip")
        self.assertEqual(github.pick_asset(self.assets("tool.exe", "tool.sha256")).name, "tool.exe")
        self.assertIsNone(github.pick_asset(self.assets("App-macos.zip", "notes.txt")))


class VersionTests(unittest.TestCase):
    def test_is_newer(self):
        self.assertTrue(github.is_newer("v3.0.0", "2.9.9"))
        self.assertTrue(github.is_newer("1.10", "1.9"))
        self.assertTrue(github.is_newer("1.0.0", "1.0.0-beta.2"))
        self.assertFalse(github.is_newer("1.0.0-rc1", "1.0.0"))
        self.assertFalse(github.is_newer("v1.0", "1.0.0"))
        self.assertFalse(github.is_newer("nightly", "1.0"))


class ClientTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def client(self, session, token=""):
        return github.GitHubClient(token=token, cache_dir=self.cache, session_factory=lambda: session)

    def test_etag_cache_and_offline_fallback(self):
        first = FakeSession([("repos/o/r", FakeResponse(200, {"full_name": "o/r", "stargazers_count": 3},
                                                       headers={"ETag": '"abc"'}))])
        repo, offline = self.client(first).repository("o/r")
        self.assertEqual((repo.stars, offline), (3, False))

        def not_modified(headers):
            self.assertEqual(headers.get("If-None-Match"), '"abc"')
            return FakeResponse(304)
        repo, offline = self.client(FakeSession([("repos/o/r", not_modified)])).repository("o/r")
        self.assertEqual((repo.stars, offline), (3, False))

        repo, offline = self.client(FakeSession([("repos/o/r", ConnectionError("down"))])).repository("o/r")
        self.assertEqual((repo.stars, offline), (3, True))

    def test_network_error_without_cache(self):
        with self.assertRaises(github.GitHubError):
            self.client(FakeSession([("repos", ConnectionError("down"))])).repository("o/r")

    def test_rate_limit_and_not_found(self):
        limited = FakeResponse(403, {}, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"})
        with self.assertRaises(github.RateLimitError):
            self.client(FakeSession([("repos", limited)])).repository("o/r")
        with self.assertRaises(github.GitHubError):
            self.client(FakeSession([])).repository("o/missing")

    def test_releases_skip_drafts_and_prereleases(self):
        data = [release_json("v2.0.0-beta", prerelease=True), release_json("v1.0.0"),
                release_json("v9", draft=True)]
        session = FakeSession([("releases", FakeResponse(200, data))])
        releases, _ = self.client(session).releases("o/r")
        self.assertEqual([r.tag for r in releases], ["v1.0.0"])
        releases, _ = self.client(session).releases("o/r", include_prerelease=True)
        self.assertEqual(sorted(r.tag for r in releases), ["v1.0.0", "v2.0.0-beta"])

    def test_token_only_goes_to_the_api(self):
        session = FakeSession([("api.github.com", FakeResponse(200, {"full_name": "o/r"})),
                               ("github.com/dl", FakeResponse(200, body=b"data"))])
        client = self.client(session, token="secret")
        client.repository("o/r")
        self.assertEqual(session.calls[-1][1].get("Authorization"), "Bearer secret")
        public = self.client(session)
        asset = github.parse_asset(asset_json("a.exe", size=4))
        public.download(asset, self.cache / "a.exe")
        self.assertNotIn("Authorization", session.calls[-1][1])

    def test_download_checks_digest_and_size(self):
        body = b"hello world!"
        good = hashlib.sha256(body).hexdigest()
        session = FakeSession([("github.com/dl", FakeResponse(200, body=body))])
        client = self.client(session)
        target = self.cache / "out" / "app.exe"
        progress = []
        client.download(github.parse_asset(asset_json("app.exe", size=len(body), digest=good)), target,
                        on_progress=lambda d, t: progress.append((d, t)))
        self.assertEqual(target.read_bytes(), body)
        self.assertEqual(progress[-1], (len(body), len(body)))

        bad = github.parse_asset(asset_json("app.exe", size=len(body), digest="0" * 64))
        with self.assertRaises(github.IntegrityError):
            client.download(bad, self.cache / "bad.exe")
        self.assertFalse((self.cache / "bad.exe").exists())
        self.assertFalse((self.cache / "bad.exe.part").exists())

        short = github.parse_asset(asset_json("app.exe", size=len(body) + 5))
        with self.assertRaises(github.IntegrityError):
            client.download(short, self.cache / "short.exe")

    def test_download_can_be_cancelled(self):
        session = FakeSession([("github.com/dl", FakeResponse(200, body=b"x" * 40))])
        with self.assertRaises(github.DownloadCancelled):
            self.client(session).download(github.parse_asset(asset_json("a.exe", size=40)),
                                          self.cache / "a.exe", cancelled=lambda: True)
        self.assertFalse((self.cache / "a.exe.part").exists())


class FakeClient:
    def __init__(self, releases, repo=None):
        self._releases = releases
        self._repo = repo or github.Repository(full_name="o/r")

    def repository(self, repo):
        return self._repo, False

    def releases(self, repo, include_prerelease=False):
        return [github.parse_release(r) for r in self._releases], False


class GitHubSourceTests(unittest.TestCase):
    def app(self, **extra):
        data = {"id": "a", "name": "App", "github": "o/r", **extra}
        return parse_config({"apps": [data]}).apps[0]

    def test_latest_is_the_newest_release_with_a_matching_asset(self):
        client = FakeClient([release_json("v2", assets=[asset_json("App-linux.tar.gz", id_=5)]),
                             release_json("v1", assets=[asset_json("App.zip", id_=7)])])
        info = sources.GitHubAppSource(self.app(), client).check()
        self.assertEqual(info.latest.label, "v1")
        self.assertEqual(info.latest.key, "github:v1:7")
        self.assertEqual([v.label for v in info.history], ["v2", "v1"])
        self.assertFalse(info.history[0].installable)

    def test_problems_are_reported(self):
        info = sources.GitHubAppSource(self.app(), FakeClient([])).check()
        self.assertIsNone(info.latest)
        self.assertTrue(info.problem)
        info = sources.GitHubAppSource(self.app(asset="*.msi"),
                                       FakeClient([release_json(assets=[asset_json("a.zip")])])).check()
        self.assertIn("*.msi", info.problem)


class NotesTests(unittest.TestCase):
    BILINGUAL = (
        "![shot](https://img/x.png)\n\n**Português** · [English below](#english)\n\n"
        "Primeira versão do app, com muitas novidades para todo mundo usar.\n\n"
        "### Destaques\n- um\n\n<a id=\"english\"></a>\n**English**\n\n"
        "First release of the app, with plenty of news for everyone to use.\n\n### Highlights\n- one\n"
    )

    def test_localized_notes_picks_the_language(self):
        en = sources.localized_notes(self.BILINGUAL, "en")
        self.assertIn("First release", en)
        self.assertNotIn("Primeira", en)
        self.assertIn("![shot]", en, "the preamble is kept")
        pt = sources.localized_notes(self.BILINGUAL, "pt-BR")
        self.assertIn("Primeira", pt)
        self.assertNotIn("First release", pt)

    def test_heading_markers_and_single_language(self):
        text = "## App v2\n\n**English** | [Português](#português)\n\nNew things.\n\n### Português\n\nCoisas novas.\n"
        self.assertIn("Coisas novas", sources.localized_notes(text, "pt-BR"))
        self.assertNotIn("Coisas novas", sources.localized_notes(text, "en"))
        plain = "Just one language.\n\n### Highlights\n- a\n"
        self.assertEqual(sources.localized_notes(plain, "pt-BR"), plain)

    def test_excerpt_and_images(self):
        notes = sources.localized_notes(self.BILINGUAL, "en")
        self.assertTrue(sources.excerpt(notes).startswith("First release of the app"))
        self.assertTrue(sources.excerpt("x " * 200, limit=40).endswith("…"))
        self.assertEqual(sources.markdown_images(self.BILINGUAL + '<img src="https://img/y.png">'),
                         ["https://img/x.png", "https://img/y.png"])


if __name__ == "__main__":
    unittest.main()
