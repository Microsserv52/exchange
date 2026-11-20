"""Local development helpers. This module is not used by the HTTP service."""

from __future__ import annotations

import argparse
import time
import uuid
from collections.abc import Sequence

import jwt

from exchange.config import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m exchange.cli")
    subcommands = parser.add_subparsers(dest="command", required=True)

    token = subcommands.add_parser("token", help="Create a local HS256 bearer token.")
    token.add_argument("--sub", default=str(uuid.uuid4()), help="Account UUID subject.")
    token.add_argument("--roles", default="ROLE_USER", help="Comma-separated roles.")
    token.add_argument("--ttl", type=int, default=3600, help="Token lifetime in seconds.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command != "token":
        return 2

    settings = get_settings()
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": arguments.sub,
        "roles": [role.strip() for role in arguments.roles.split(",") if role.strip()],
        "iat": now,
        "exp": now + max(60, min(arguments.ttl, 86400)),
    }
    if settings.jwt_issuer:
        payload["iss"] = settings.jwt_issuer
    if settings.jwt_audience:
        payload["aud"] = settings.jwt_audience
    token = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
