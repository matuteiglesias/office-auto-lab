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


def _diagnose_x_failure(raw: str) -> str:
    """Return a fixed safe classification; NEVER return original provider text."""
    lower = raw.casefold()
    if "tokennotfound" in lower or "token not found" in lower:
        return "NO_OAUTH1_TOKEN_LOADED"
    if "client-not-enrolled" in lower or "client_not_enrolled" in lower:
        return "X_APP_NOT_ENROLLED_IN_API_PACKAGE"
    if "client-forbidden" in lower or "client_forbidden" in lower:
        return "X_APP_NOT_ENROLLED_IN_API_PACKAGE"
    if "invalid or expired token" in lower or "could not authenticate you" in lower:
        return "X_INVALID_OR_EXPIRED_USER_TOKEN"
    if "signature" in lower and ("invalid" in lower or "failed" in lower):
        return "X_OAUTH1_SIGNATURE_OR_KEY_PAIR_MISMATCH"
    if "403" in lower or "forbidden" in lower or "not enrolled" in lower:
        return "X_APP_PERMISSION_OR_PACKAGE_BLOCKED"
    if "429" in lower or "rate limit" in lower:
        return "X_RATE_LIMITED"
    if "401" in lower or "unauthorized" in lower:
        return "X_REJECTED_OAUTH1_CREDENTIALS_OR_APP_ACCESS"
    return "X_WHOAMI_COMMAND_FAILED"


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
            reason = _diagnose_x_failure(detail)
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
        # Check xurl recognizes the freshly serialized OAuth1 token.
        # Do not print the store or any credential-bearing content.
        status = _command([binary, "auth", "status"], env=env, stage="XURL_TOKEN_STORE")
        if APP not in status or "oauth1: ✓" not in status:
            raise BootstrapBlocked("XURL_TOKEN_STORE: OAUTH1_NOT_LOADED")
        print("xurl token store: isolated economics OAuth1 credential recognized.")
        # Read-only X API identity proof; no posting or refresh.
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


def _gh_variable_upsert(name: str, value: str) -> None:
    """Set one nonsecret repo variable via gh api, including older gh versions.

    GitHub REST provides POST /actions/variables and PATCH /actions/variables/{name}.
    Check whether the variable exists; only a confirmed HTTP 404 permits create.
    Never expose X secrets through this operation.
    """
    endpoint = f"repos/{REPO}/actions/variables"
    try:
        check = subprocess.run(
            ["gh", "api", "-X", "GET", f"{endpoint}/{name}"],
            capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BootstrapBlocked(f"GITHUB_VARIABLE_{name}: lookup command unavailable") from exc
    if check.returncode == 0:
        _command(
            ["gh", "api", "-X", "PATCH", f"{endpoint}/{name}",
             "-f", f"name={name}", "-f", f"value={value}"],
            stage=f"GITHUB_VARIABLE_{name}_UPDATE",
        )
    elif "HTTP 404" in check.stderr or "HTTP 404" in check.stdout:
        _command(
            ["gh", "api", "-X", "POST", endpoint,
             "-f", f"name={name}", "-f", f"value={value}"],
            stage=f"GITHUB_VARIABLE_{name}_CREATE",
        )
    else:
        # A 401/403/transport failure must not be misinterpreted as absent.
        raise BootstrapBlocked(
            f"GITHUB_VARIABLE_{name}: lookup failed (check GitHub auth and Actions-variable permission)"
        )


def _configure_disabled_variables() -> None:
    """First establish GitHub write permissions without asking for X secrets."""
    for key, value in DISABLED_VARIABLES.items():
        _gh_variable_upsert(key, value)
    print("GitHub Actions variables written; scheduler and publisher are disabled.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure economics GitHub Actions OAuth1 without showing tokens")
    parser.add_argument("--apply", action="store_true", help="verify economics credentials and set GitHub secret, leaving publication disabled")
    parser.add_argument("--configure-github-only", action="store_true", help="set only nonsecret disabled GitHub variables; no X credentials")
    args = parser.parse_args()
    if not args.apply and not args.configure_github_only:
        print("Use --configure-github-only to test GitHub variable writes without asking for X credentials.")
        print("Use --apply after the GitHub variables have been configured successfully.")
        return 0
    if args.apply and args.configure_github_only:
        parser.error("choose --apply or --configure-github-only")
    try:
        _command(["gh", "auth", "status"], stage="GITHUB_AUTH")
        # IMPORTANT: GH permission errors must fail before the operator has to
        # retype credentials. These values contain no X secrets.
        _configure_disabled_variables()
        if args.configure_github_only:
            return 0
        if not sys.stdin.isatty():
            raise BootstrapBlocked("a private interactive operator terminal is required")
        xurl = shutil.which("xurl") or str(Path.home() / ".local" / "bin" / "xurl")
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
        # The variables were already forced to safe defaults above.
        # The X secret is sent via stdin, never displayed or persisted here.
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
