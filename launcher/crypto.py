"""Cifra simples (stdlib) para guardar senhas em JSON publicado.

Formato V1 — `b"V1" | salt(16) | hmac(32) | ciphertext`, codificado em base64:
  - PBKDF2-HMAC-SHA256 (200 000 iterações) deriva 64 bytes de `secret + salt`;
  - os 32 primeiros bytes semeiam um keystream SHA-256 em counter mode (XOR);
  - os 32 últimos são a chave do HMAC-SHA256 sobre `salt + ciphertext`.

É ofuscação com integridade, não um cofre: quem tem o segredo (embutido na
configuração do launcher) decifra o token. Serve para que um JSON acessível
por link não exponha a senha em texto puro.

Para gerar tokens: `python -m tools.encrypt_password`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

MAGIC = b"V1"
ITERATIONS = 200_000


def generate_secret() -> str:
    """Novo segredo aleatório de 32 bytes, em base64."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


def _decode_secret(secret: str) -> bytes:
    try:
        raw = base64.b64decode(secret, validate=True)
    except Exception:
        raise ValueError("segredo inválido: esperado base64") from None
    if len(raw) < 16:
        raise ValueError("segredo curto demais (mínimo 16 bytes)")
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
    """Decifra um token V1. Levanta ValueError em qualquer falha."""
    key = _decode_secret(secret)
    try:
        blob = base64.b64decode(token, validate=True)
    except Exception as exc:
        raise ValueError(f"token base64 inválido: {exc}") from None
    if len(blob) < 50 or blob[:2] != MAGIC:
        raise ValueError("formato de token não reconhecido")
    salt, mac, ct = blob[2:18], blob[18:50], blob[50:]
    k_enc, k_mac = _derive_keys(key, salt)
    if not hmac.compare_digest(mac, hmac.new(k_mac, salt + ct, hashlib.sha256).digest()):
        raise ValueError("HMAC inválido — segredo incorreto ou token adulterado")
    plain = bytes(a ^ b for a, b in zip(ct, _keystream(k_enc, len(ct))))
    return plain.decode("utf-8")
