import tempfile
import unittest
from pathlib import Path

from launcher import crypto
from launcher.config import ServerConfig
from launcher.remote import CredentialsError, _parse_sha256, resolve_credentials
from launcher.state import StateStore


class CryptoTests(unittest.TestCase):
    def test_round_trip(self):
        secret = crypto.generate_secret()
        token = crypto.encrypt("Senha^Com~Acento", secret)
        self.assertEqual(crypto.decrypt(token, secret), "Senha^Com~Acento")

    def test_tokens_are_salted(self):
        secret = crypto.generate_secret()
        self.assertNotEqual(crypto.encrypt("x", secret), crypto.encrypt("x", secret))

    def test_wrong_secret_fails(self):
        token = crypto.encrypt("x", crypto.generate_secret())
        with self.assertRaises(ValueError):
            crypto.decrypt(token, crypto.generate_secret())

    def test_tampered_token_fails(self):
        secret = crypto.generate_secret()
        token = bytearray(crypto.encrypt("abcdef", secret).encode())
        token[-3] = ord("A") if token[-3] != ord("A") else ord("B")
        with self.assertRaises(ValueError):
            crypto.decrypt(token.decode(), secret)


class ResolveCredentialsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(Path(self._tmp.name) / "state.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_static_config(self):
        creds = resolve_credentials(ServerConfig(host="h", port=2121, user="u", password="p"))
        self.assertEqual((creds.host, creds.port, creds.user, creds.password), ("h", 2121, "u", "p"))

    def test_static_encrypted_password(self):
        secret = crypto.generate_secret()
        server = ServerConfig(host="h", password_enc=crypto.encrypt("segredo", secret), secret=secret)
        self.assertEqual(resolve_credentials(server).password, "segredo")

    def test_encrypted_password_without_secret(self):
        with self.assertRaises(CredentialsError):
            resolve_credentials(ServerConfig(host="h", password_enc="abc"))

    def test_remote_json_is_cached(self):
        server = ServerConfig(credentials_url="https://example/creds.json")
        creds = resolve_credentials(server, self.store,
                                    fetch=lambda url: {"host": "remote", "user": "r", "password": "pw"})
        self.assertEqual(creds.host, "remote")

        def offline(url):
            raise ConnectionError("offline")

        cached = resolve_credentials(server, self.store, fetch=offline)
        self.assertEqual(cached, creds)

    def test_remote_failure_without_cache(self):
        def offline(url):
            raise ConnectionError("offline")

        with self.assertRaises(CredentialsError):
            resolve_credentials(ServerConfig(credentials_url="https://x"), self.store, fetch=offline)


class Sha256ParsingTests(unittest.TestCase):
    def test_plain_and_sha256sum_formats(self):
        digest = "a" * 64
        self.assertEqual(_parse_sha256(digest), digest)
        self.assertEqual(_parse_sha256(f"{digest.upper()}  file.zip\n"), digest)

    def test_rejects_garbage(self):
        self.assertIsNone(_parse_sha256("not a hash"))
        self.assertIsNone(_parse_sha256(""))
        self.assertIsNone(_parse_sha256(None))


if __name__ == "__main__":
    unittest.main()
