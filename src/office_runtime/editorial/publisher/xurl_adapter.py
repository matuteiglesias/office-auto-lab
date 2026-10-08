from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class XurlError(RuntimeError):
    pass


@dataclass(frozen=True)
class XIdentity:
    username: str
    user_id: str


@dataclass(frozen=True)
class XPost:
    post_id: str
    text: str
    username: str | None = None
    author_id: str | None = None
    created_at: str | None = None


def _json_output(stdout: str, operation: str) -> Mapping[str, Any]:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise XurlError(f"xurl {operation} returned non-JSON output") from exc
    if not isinstance(value, Mapping):
        raise XurlError(f"xurl {operation} returned a non-object response")
    return value


def _data(response: Mapping[str, Any]) -> Mapping[str, Any]:
    value = response.get("data", response)
    return value if isinstance(value, Mapping) else {}


def _xurl_binary() -> str:
    configured = os.environ.get("XURL_BIN")
    if configured:
        return configured
    discovered = shutil.which("xurl")
    if discovered:
        return discovered
    for candidate in (Path.home() / ".local/bin/xurl", Path.home() / ".n/bin/xurl"):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "xurl"


def _run(args: list[str], operation: str) -> Mapping[str, Any]:
    command = [_xurl_binary(), "--app", "modernai-editorial", "--auth", "oauth1", *args]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise XurlError(f"cannot execute xurl for {operation}") from exc
    if completed.returncode != 0:
        raise XurlError(f"xurl {operation} failed with exit {completed.returncode}")
    return _json_output(completed.stdout, operation)


def _post_from(value: Mapping[str, Any], response: Mapping[str, Any] | None = None) -> XPost:
    post_id = str(value.get("id", ""))
    text = value.get("text")
    if not post_id or not isinstance(text, str):
        raise XurlError("xurl response did not contain a post id and text")
    username = value.get("username")
    author_id = value.get("author_id")
    if response:
        users = response.get("includes", {}).get("users", [])
        if isinstance(users, list) and users:
            user = users[0]
            if isinstance(user, Mapping):
                username = user.get("username", username)
                author_id = user.get("id", author_id)
    return XPost(
        post_id=post_id,
        text=text,
        username=username if isinstance(username, str) else None,
        author_id=author_id if isinstance(author_id, str) else None,
        created_at=value.get("created_at") if isinstance(value.get("created_at"), str) else None,
    )


class XurlAdapter:
    """Small OAuth1 xurl transport; credentials remain owned by xurl."""

    def whoami(self) -> XIdentity:
        value = _data(_run(["whoami"], "whoami"))
        username = value.get("username")
        user_id = value.get("id")
        if not isinstance(username, str) or not isinstance(user_id, str):
            raise XurlError("whoami response did not contain username and id")
        return XIdentity(username=username, user_id=user_id)

    def recent_posts(self, username: str, max_results: int = 100) -> list[XPost]:
        value = _run(["posts", username, "-n", str(max_results)], "posts")
        raw = value.get("data", [])
        if not isinstance(raw, list):
            raise XurlError("posts response did not contain a data array")
        return [_post_from(item) for item in raw if isinstance(item, Mapping)]

    def create_post(self, text: str) -> XPost:
        return _post_from(_data(_run(["post", text], "post")))

    def read_post(self, post_id: str) -> XPost:
        response = _run(["read", post_id], "read")
        return _post_from(_data(response), response)
