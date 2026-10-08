"""Strict GET-only X API transport, separate from mutation-capable publisher xurl."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import ObserverContractError, numeric_id

HOST = "https://api.x.com/2"
HANDLE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
POST_FIELDS = "created_at,conversation_id,lang,edit_history_post_ids"
EXPANSIONS = "referenced_posts,author_id"
USER_FIELDS = "protected"
MAX_RESPONSE_BYTES = 2_000_000


class XObserverAPIError(RuntimeError):
    """Only sanitized status and operation; never source body or bearer token."""


def timeline_params(*, max_results: int, pagination_token: str | None = None) -> dict[str, str]:
    if not 5 <= max_results <= 100:
        raise ObserverContractError("max_results must be 5..100")
    params = {
        "max_results": str(max_results),
        "post.fields": POST_FIELDS,
        "expansions": EXPANSIONS,
        "user.fields": USER_FIELDS,
    }
    if pagination_token is not None:
        if not pagination_token or len(pagination_token) > 1000:
            raise ObserverContractError("pagination token is malformed")
        params["pagination_token"] = pagination_token
    # In particular, no exclude=retweets/replies.
    return params


class ReadOnlyXClient:
    def __init__(self, bearer_token: str, *, timeout: float = 15) -> None:
        if not bearer_token or not bearer_token.strip():
            raise ObserverContractError("separate observer bearer token is required")
        self.__bearer = bearer_token.strip()
        self.timeout = timeout

    def _get(self, path: str, params: Mapping[str, str]) -> dict[str, Any]:
        if not path.startswith("/users/") or not re.fullmatch(r"/users/(?:by/username/[A-Za-z0-9_]{1,15}|[0-9]{1,19}/tweets)", path):
            raise ObserverContractError("observer client is restricted to user lookup and public user posts")
        url = HOST + path + "?" + urlencode(dict(params))
        req = Request(url, headers={"Authorization": "Bearer " + self.__bearer,
                                    "Accept": "application/json"}, method="GET")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise XObserverAPIError("X response exceeds byte limit")
        except HTTPError as exc:
            # Do not log HTTP body, headers, URL/query or raw error.
            raise XObserverAPIError(f"X read blocked (HTTP {exc.code})") from None
        except (OSError, URLError, TimeoutError):
            raise XObserverAPIError("X read transport unavailable") from None
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise XObserverAPIError("X returned non-JSON response") from None
        if not isinstance(result, dict):
            raise XObserverAPIError("X returned a non-object response")
        return result

    def resolve_user(self, handle: str) -> Mapping[str, Any]:
        if not HANDLE.fullmatch(handle):
            raise ObserverContractError("invalid X handle")
        response = self._get("/users/by/username/" + handle, {"user.fields": USER_FIELDS})
        if response.get("errors") or not isinstance(response.get("data"), Mapping):
            raise XObserverAPIError("X account lookup failed or was partial")
        user = response["data"]
        numeric_id(user.get("id"), "resolved X account ID")
        if str(user.get("username", "")).casefold() != handle.casefold():
            raise ObserverContractError("X resolved a different username")
        if user.get("protected") is not False:
            raise ObserverContractError("X subject is protected or public status is unverified")
        return user

    def user_posts(self, user_id: str, *, max_results: int,
                   pagination_token: str | None = None) -> Mapping[str, Any]:
        numeric_id(user_id, "observed user ID")
        return self._get("/users/" + user_id + "/tweets",
                         timeline_params(max_results=max_results, pagination_token=pagination_token))
