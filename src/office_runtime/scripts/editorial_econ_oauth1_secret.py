"""Restore economics-only static OAuth1 identity from one GitHub Actions secret.

No API or Google Cloud dependency. This is intentionally NOT a token refresh
service: OAuth1 credentials remain stable until operator revocation or rotation.
The calling workflow provides a temporary HOME; no developer-account token
may be included in the economics secret.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

APP_NAME = "argentina-econ-editorial"
SECRET_ENV = "EDITORIAL_ECON_XURL_OAUTH1_YAML"


def validate(data: str) -> dict:
    document = yaml.safe_load(data)
    if not isinstance(document, dict):
        raise ValueError("secret must be YAML mapping")
    apps = document.get("apps")
    if not isinstance(apps, dict) or set(apps) != {APP_NAME}:
        raise ValueError("secret must contain exactly the economics X app")
    if document.get("default_app") != APP_NAME:
        raise ValueError("default_app must be the economics X app")
    app = apps[APP_NAME]
    if not isinstance(app, dict):
        raise ValueError("economics app must be an object")
    if app.get("oauth2_tokens") or app.get("bearer_token"):
        raise ValueError("OAuth2 and app bearer credentials are prohibited")
    token = app.get("oauth1_token")
    if not isinstance(token, dict) or token.get("type") != "oauth1":
        raise ValueError("one OAuth1 user token is required")
    credentials = token.get("oauth1")
    if not isinstance(credentials, dict) or any(
        not isinstance(credentials.get(name), str) or not credentials[name]
        for name in ("access_token", "token_secret", "consumer_key", "consumer_secret")
    ):
        raise ValueError("OAuth1 token has incomplete credentials")
    return document


def main() -> int:
    try:
        secret = os.environ.get(SECRET_ENV, "")
        if not secret:
            raise ValueError("economics-only GitHub secret is not configured")
        validate(secret)
        home = Path(os.environ["HOME"])
        directory = home / ".xurl"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
        path = directory / "auth.yml"
        if path.exists():
            raise ValueError("refusing to overwrite pre-existing X authentication")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(secret.rstrip("\n") + "\n")
        print("Economics-only OAuth1 credentials loaded into ephemeral runner.")
        return 0
    except Exception as exc:
        # Never print secret contents or parse exception string.
        print(f"::error::Economics OAuth1 preflight blocked ({type(exc).__name__}).", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
