"""One-time LOCAL operator bootstrap: economics OAuth1 -> GitHub Actions Secret.

Run interactively in the user's own terminal:
  PYTHONPATH=src python -m office_runtime.scripts.editorial_econ_actions_setup --apply

Never invoke this command from a remote agent or log the entered credentials.
It does not touch existing ~/.xurl/auth.yml, does not post, and disables
all economics scheduled/live switches in GitHub before returning.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from office_runtime.scripts.editorial_econ_oauth1_secret import validate

REPO = "matuteiglesias/office-auto-lab"
APP = "argentina-econ-editorial"
ID = "57242581"
USERNAME = "matuteiglesias"
SHEET_ID = "1LAVlYY3T7POA3IUydn3zy2MQBrxc-3c1w-iUq7oFtgo"

DISABLED_VARIABLES = {
    "EDITORIAL_ARGENTINA_ECON_SHEET_ID": SHEET_ID,
    "EDITORIAL_ECON_SCHEDULER_ENABLED": "false",
    "EDITORIAL_ECON_PUBLISH_ENABLED": "false",
    "EDITORIAL_ECON_RUNTIME_PROMOTED": "false",
    "EDITORIAL_ARGENTINA_ECON_PUBLISHER_DISABLED": "1",
}


class BootstrapBlocked(RuntimeError):
    pass


def _command(argv: list[str], *, input_data: str | None = None, env: dict[str, str] | None = None, stage: str = "COMMAND") -> str:
    try:
        result = subprocess.run(
            argv, input=input_data, text=True, capture_output=True,
            check=False, env=env, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BootstrapBlocked(f"{stage}: command unavailable or timed out") from exc
    if result.returncode != 0:
        # Classify known public provider error codes; never echo raw stderr/stdout,
        # since CLI tools may unintentionally include tokens in diagnostics.
        detail = (result.stderr + "\n" + result.stdout).casefold()
        if stage == "X_WHOAMI":
            if "tokennotfound" in detail or "token not found" in detail:
                reason = "NO_OAUTH1_TOKEN_LOADED"
            elif "401" in detail or "unauthorized" in detail:
                reason = "X_REJECTED_OAUTH1_CREDENTIALS"
            elif "403" in detail or "forbidden" in detail or "not enrolled" in detail:
                reason = "X_APP_PERMISSION_OR_PACKAGE_BLOCKED"
            elif "429" in detail or "rate limit" in detail:
                reason = "X_RATE_LIMITED"
            else:
                reason = "X_WHOAMI_COMMAND_FAILED"
            raise BootstrapBlocked(f"{stage}: {reason} (exit {result.returncode})")
        raise BootstrapBlocked(f"{stage}: command failed (exit {result.returncode})")
    return result.stdout


def _verify_xurl(binary: str, auth: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="econ-xurl-proof-") as work:
        home = Path(work)
        (home / ".xurl").mkdir(mode=0o700)
        path = home / ".xurl" / "auth.yml"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(auth)
        env = os.environ.copy()
        env["HOME"] = str(home)
        # Only a read-only identity proof. No app post or OAuth2 refresh.
        raw = _command([binary, "--app", APP, "--auth", "oauth1", "whoami"], env=env, stage="X_WHOAMI")
        try:
            decoded = json.loads(raw)
            user = decoded.get("data", decoded)
            username, user_id = user.get("username"), str(user.get("id", ""))
        except (ValueError, AttributeError, TypeError) as exc:
            raise BootstrapBlocked("xurl whoami did not return a valid identity response") from exc
        if username is None or user_id == "":
            raise BootstrapBlocked("X_WHOAMI: INVALID_ACCOUNT_RESPONSE")
        if username.casefold() != USERNAME.casefold() or user_id != ID:
            # User IDs are public, never credentials. Don't print incoming tokens.
            raise BootstrapBlocked(f"X_WHOAMI: WRONG_ACCOUNT (expected @{USERNAME} / {ID}; got @{username} / {user_id})")
        return username, user_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure economics GitHub Actions OAuth1 without showing tokens")
    parser.add_argument("--apply", action="store_true", help="actually write only the economics GitHub secret and disabled variables")
    args = parser.parse_args()
    if not args.apply:
        print("Dry description only: use --apply in your OWN interactive terminal to enter four X OAuth1 values.")
        print("No X publication, no local OAuth2 modification; GitHub publication switches remain disabled.")
        return 0
    try:
        if not sys.stdin.isatty():
            raise BootstrapBlocked("a private interactive operator terminal is required")
        xurl = shutil.which("xurl") or str(Path.home() / ".local" / "bin" / "xurl")
        _command(["gh", "auth", "status"], stage="GITHUB_AUTH")
        _command([xurl, "--version"], stage="XURL_PREFLIGHT")
        prompts = {
            "consumer_key": "Economics app API key (OAuth1)",
            "consumer_secret": "Economics app API key secret",
            "access_token": "Economics @matuteiglesias access token",
            "token_secret": "Economics @matuteiglesias access token secret",
        }
        values = {}
        for key, label in prompts.items():
            value = getpass.getpass(label + ": ").strip()
            if not value:
                raise BootstrapBlocked("one or more X OAuth1 values are blank")
            values[key] = value
        auth = yaml.safe_dump({
            "default_app": APP,
            "apps": {APP: {"oauth1_token": {"type": "oauth1", "oauth1": values}}},
        }, sort_keys=False)
        validate(auth)
        print("Checking economics OAuth1 identity with X (read-only). No secrets will be logged.")
        _verify_xurl(xurl, auth)
        print("Verified isolated economics OAuth1 identity: @matuteiglesias / 57242581.")
        # Lock mutation before writing any secret, including during re-runs.
        for key, value in DISABLED_VARIABLES.items():
            _command(["gh", "variable", "set", key, "--repo", REPO, "--body", value], stage=f"GITHUB_VARIABLE_{key}")
        _command(["gh", "secret", "set", "EDITORIAL_ECON_XURL_OAUTH1_YAML", "--repo", REPO], input_data=auth, stage="GITHUB_SECRET")
        print("Economics-only GitHub Actions secret configured, with ALL publication switches disabled.")
        print("Next: CI + merge PR #74, then dispatch two independent dry-runs. No live post was sent.")
        return 0
    except BootstrapBlocked as exc:
        # Only internally composed, explicitly sanitized stage/reason strings.
        print(f"Bootstrap blocked: {exc}. No credential values were displayed.", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Bootstrap blocked: UNEXPECTED_{type(exc).__name__}. Credentials were not displayed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
