"""GitHub Actions-only xurl OAuth2 state transport.

No X API calls here. The authoritative encrypted-at-rest GCS object contains
ONLY the argentina-econ-editorial app, never the developer app. This module
never prints credentials or uploads them as GitHub Actions artifacts.

RESTORE before an xurl invocation; PERSIST in an always() cleanup step. An
optimistic GCS generation precondition refuses concurrent/stale overwrites.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml
from google.cloud import storage
from google.oauth2 import service_account

APP = "argentina-econ-editorial"
EXPECTED_USER = "matuteiglesias"
KEY_PREFIX = "auth/argentina_econ/"


class AuthStoreError(RuntimeError):
    pass


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise AuthStoreError(f"{name} is required")
    return value


def _paths() -> tuple[Path, Path]:
    home = Path(_required("HOME"))
    base = home / ".xurl"
    return base / "auth.yml", base / ".econ-gcs-state.json"


def _read_yaml(raw: bytes) -> dict[str, Any]:
    try:
        config = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise AuthStoreError("invalid economics-only xurl YAML") from exc
    if not isinstance(config, dict):
        raise AuthStoreError("xurl state must be a mapping")
    apps = config.get("apps")
    if not isinstance(apps, dict) or set(apps) != {APP}:
        raise AuthStoreError("xurl auth state must contain ONLY argentina-econ-editorial")
    app = apps[APP]
    if not isinstance(app, dict):
        raise AuthStoreError("economics xurl app must be a mapping")
    users = app.get("oauth2_tokens")
    if not isinstance(users, dict) or set(users) != {EXPECTED_USER}:
        raise AuthStoreError("economics xurl OAuth2 state must contain ONLY matuteiglesias")
    if not app.get("client_id") or not app.get("client_secret"):
        raise AuthStoreError("economics xurl app is missing OAuth2 client credentials")
    token = users[EXPECTED_USER]
    if not isinstance(token, dict):
        raise AuthStoreError("economics OAuth2 token is invalid")
    # Avoid assuming xurl's nested token structure; require a refresh token
    # somewhere in the one allowed user's token subtree.
    def has_refresh(value: Any) -> bool:
        if isinstance(value, dict):
            if isinstance(value.get("refresh_token"), str) and value["refresh_token"]:
                return True
            return any(has_refresh(item) for item in value.values())
        return False
    if not has_refresh(token):
        raise AuthStoreError("economics OAuth2 token has no durable refresh token")
    return config


def _blob() -> storage.Blob:
    try:
        info = json.loads(_required("EDITORIAL_GOOGLE_CREDENTIALS_JSON"))
        if info.get("type") != "service_account":
            raise AuthStoreError("Google credentials must be a service account")
        creds = service_account.Credentials.from_service_account_info(info)
        client = storage.Client(project=info.get("project_id"), credentials=creds)
        bucket = _required("EDITORIAL_ECON_AUTH_GCS_BUCKET")
        key = _required("EDITORIAL_ECON_AUTH_GCS_OBJECT")
        if not key.startswith(KEY_PREFIX):
            raise AuthStoreError("economics auth object must be under " + KEY_PREFIX)
        return client.bucket(bucket).blob(key)
    except (ValueError, KeyError, TypeError) as exc:
        raise AuthStoreError("invalid Google service-account credential configuration") from exc


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
    finally:
        path.chmod(0o600)


def restore() -> None:
    auth_path, state_path = _paths()
    if auth_path.exists() or state_path.exists():
        raise AuthStoreError("will not restore over existing local xurl auth state")
    blob = _blob()
    blob.reload()
    generation = blob.generation
    if generation is None:
        raise AuthStoreError("GCS OAuth2 object has no generation")
    raw = blob.download_as_bytes(if_generation_match=int(generation))
    _read_yaml(raw)
    _write_private(auth_path, raw)
    state = {"generation": int(generation), "sha256": hashlib.sha256(raw).hexdigest()}
    _write_private(state_path, (json.dumps(state, sort_keys=True) + "\n").encode("utf-8"))
    print("Restored economics-only OAuth2 state; no token contents displayed.")


def persist() -> None:
    auth_path, state_path = _paths()
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        generation = int(state["generation"])
        previous_sha = str(state["sha256"])
        raw = auth_path.read_bytes()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AuthStoreError("restored OAuth2 state is unavailable for persist") from exc
    _read_yaml(raw)
    current_sha = hashlib.sha256(raw).hexdigest()
    if current_sha == previous_sha:
        print("OAuth2 state unchanged; no cloud write required.")
        return
    blob = _blob()
    # CAS: refuse if an independent publisher or administrator changed state.
    blob.upload_from_string(
        raw,
        content_type="application/x-yaml",
        if_generation_match=generation,
    )
    print("Persisted refreshed economics OAuth2 state with GCS generation precondition.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore/persist economics-only xurl OAuth2 state")
    parser.add_argument("operation", choices=("restore", "persist"))
    args = parser.parse_args()
    try:
        restore() if args.operation == "restore" else persist()
    except Exception as exc:
        # Print only a safe class name, never exception bodies potentially
        # containing GCS keys/response details.
        print(f"::error::Economics OAuth2 {args.operation} failed: {type(exc).__name__}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
