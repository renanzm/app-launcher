"""Generates the `password_enc` token for the server password.

Usage:
    python -m tools.encrypt_password --new-secret     # creates a new secret
    python -m tools.encrypt_password --secret <base64>

The secret goes in `server.secret` in launcher_config.json; the token goes in
`password_enc` (in the configuration or in the JSON that `credentials_url` points to).
"""

import argparse
import sys
from getpass import getpass

from launcher import crypto


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--secret", help="existing secret (base64)")
    group.add_argument("--new-secret", action="store_true", help="generate a new secret")
    args = parser.parse_args()

    secret = crypto.generate_secret() if args.new_secret else args.secret
    password = getpass("Server password (hidden): ")
    if not password:
        print("Empty password.", file=sys.stderr)
        return 1

    token = crypto.encrypt(password, secret)
    if crypto.decrypt(token, secret) != password:
        print("Token verification failed.", file=sys.stderr)
        return 2

    if args.new_secret:
        print(f'\n"secret": "{secret}",')
    print(f'"password_enc": "{token}"\n')
    return 0


if __name__ == "__main__":
    sys.exit(main())
