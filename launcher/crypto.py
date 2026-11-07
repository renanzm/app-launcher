"""Simple cipher (stdlib only) for storing passwords in a published JSON.

V1 format — `b"V1" | salt(16) | hmac(32) | ciphertext`, base64-encoded:
  - PBKDF2-HMAC-SHA256 (200,000 iterations) derives 64 bytes from `secret + salt`;
  - the first 32 bytes seed a SHA-256 keystream in counter mode (XOR);
  - the last 32 are the HMAC-SHA256 key over `salt + ciphertext`.

It is obfuscation with integrity, not a vault: whoever has the secret (embedded
in the launcher configuration) can decrypt the token. It exists so that a JSON
reachable by link does not expose the password in plain text.

To generate tokens: `python -m tools.encrypt_password`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from .i18n import tr

MAGIC = b"V1"
ITERATIONS = 200_000


def generate_secret() -> str:
    """New random 32-byte secret, base64-encoded."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


def _decode_secret(secret: str) -> bytes:
    try:
        raw = base64.b64decode(secret, validate=True)
    except Exception:
        raise ValueError(tr("Invalid secret: base64 expected")) from None
    if len(raw) < 16:
        raise ValueError(tr("Secret too short (minimum 16 bytes)"))
    return raw


def _derive_keys(secret: bytes, salt: bytes):
    km = hashlib.pbkdf2_hmac("sha256", secret, salt, ITERATIONS, dklen=64)
    return km[:32], km[32:]


def _keystream(seed: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        out.extend(hashlib.sha256(seed + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(out[:n])


def encrypt(plaintext: str, secret: str) -> str:
    key = _decode_secret(secret)
    salt = os.urandom(16)
    k_enc, k_mac = _derive_keys(key, salt)
    data = plaintext.encode("utf-8")
    ct = bytes(a ^ b for a, b in zip(data, _keystream(k_enc, len(data))))
    mac = hmac.new(k_mac, salt + ct, hashlib.sha256).digest()
    return base64.b64encode(MAGIC + salt + mac + ct).decode("ascii")


def decrypt(token: str, secret: str) -> str:
    """Decrypts a V1 token. Raises ValueError on any failure."""
    key = _decode_secret(secret)
    try:
        blob = base64.b64decode(token, validate=True)
    except Exception as exc:
        raise ValueError(tr("Invalid base64 token: {error}", error=exc)) from None
    if len(blob) < 50 or blob[:2] != MAGIC:
        raise ValueError(tr("Unrecognised token format"))
    salt, mac, ct = blob[2:18], blob[18:50], blob[50:]
    k_enc, k_mac = _derive_keys(key, salt)
    if not hmac.compare_digest(mac, hmac.new(k_mac, salt + ct, hashlib.sha256).digest()):
        raise ValueError(tr("Invalid HMAC — wrong secret or tampered token"))
    plain = bytes(a ^ b for a, b in zip(ct, _keystream(k_enc, len(ct))))
    return plain.decode("utf-8")
