"""Gera o token `password_enc` da senha do servidor.

Uso:
    python -m tools.encrypt_password --new-secret     # cria um segredo novo
    python -m tools.encrypt_password --secret <base64>

O segredo vai em `server.secret` no launcher_config.json; o token vai em
`password_enc` (na configuração ou no JSON apontado por `credentials_url`).
"""

import argparse
import sys
from getpass import getpass

from launcher import crypto


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--secret", help="segredo existente (base64)")
    group.add_argument("--new-secret", action="store_true", help="gera um segredo novo")
    args = parser.parse_args()

    secret = crypto.generate_secret() if args.new_secret else args.secret
    password = getpass("Senha do servidor (não será exibida): ")
    if not password:
        print("Senha vazia.", file=sys.stderr)
        return 1

    token = crypto.encrypt(password, secret)
    if crypto.decrypt(token, secret) != password:
        print("Falha na verificação do token.", file=sys.stderr)
        return 2

    if args.new_secret:
        print(f'\n"secret": "{secret}",')
    print(f'"password_enc": "{token}"\n')
    return 0


if __name__ == "__main__":
    sys.exit(main())
