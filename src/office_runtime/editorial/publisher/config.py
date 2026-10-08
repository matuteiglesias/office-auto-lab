from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class PublisherConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublisherConfig:
    profile_id: str
    account_key: str
    sheet_id_env: str
    xurl_app: str
    xurl_auth: str
    expected_username: str
    expected_user_id: str
    receipt_namespace: str
    kill_switch_env: str
    max_posts_per_day: int
    min_post_gap_hours: int
    require_manual_seed: bool
    authorized_candidate_ids: frozenset[str]

    @classmethod
    def from_profile(cls, profile_id: str, path: Path | None = None) -> "PublisherConfig":
        source = path or Path(__file__).parents[4] / "config/editorial/profiles.json"
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PublisherConfigError("cannot read editorial profile configuration") from exc
        profiles = payload.get("profiles") if isinstance(payload, Mapping) else None
        if not isinstance(profiles, list):
            raise PublisherConfigError("editorial profile configuration has no profiles")
        profile = next((item for item in profiles if isinstance(item, Mapping) and item.get("profile_id") == profile_id), None)
        if profile is None:
            raise PublisherConfigError(f"unknown publisher profile {profile_id!r}")
        publication = profile.get("publication")
        publisher = profile.get("publisher")
        if not isinstance(publication, Mapping) or not isinstance(publisher, Mapping):
            raise PublisherConfigError(f"profile {profile_id!r} lacks complete publisher configuration")
        required = ("sheet_id_env", "xurl_app", "xurl_auth", "expected_username", "expected_user_id", "receipt_namespace", "kill_switch_env")
        if any(not isinstance(publisher.get(key), str) or not publisher.get(key) for key in required):
            raise PublisherConfigError(f"profile {profile_id!r} has incomplete publisher bindings")
        authorized = publisher.get("authorized_candidate_ids", [])
        if not isinstance(authorized, list) or not all(isinstance(value, str) for value in authorized):
            raise PublisherConfigError("authorized_candidate_ids must be a string array")
        return cls(
            profile_id=profile_id,
            account_key=str(profile.get("account_key", "")),
            sheet_id_env=str(publisher["sheet_id_env"]),
            xurl_app=str(publisher["xurl_app"]),
            xurl_auth=str(publisher["xurl_auth"]),
            expected_username=str(publisher["expected_username"]),
            expected_user_id=str(publisher["expected_user_id"]),
            receipt_namespace=str(publisher["receipt_namespace"]),
            kill_switch_env=str(publisher["kill_switch_env"]),
            max_posts_per_day=int(publication.get("max_posts_per_day", 1)),
            min_post_gap_hours=int(publisher.get("min_post_gap_hours", 5)),
            require_manual_seed=bool(publisher.get("require_manual_seed", False)),
            authorized_candidate_ids=frozenset(authorized),
        )
