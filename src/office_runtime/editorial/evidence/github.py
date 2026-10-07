from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..contracts import ActivityEvidence, ContractError


class GitHubTransport(Protocol):
    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any: ...


class GitHubHTTPError(RuntimeError):
    def __init__(self, status_code: int | None, failure_kind: str) -> None:
        super().__init__(f"GitHub read failed: {failure_kind}")
        self.status_code = status_code
        self.failure_kind = failure_kind


class GitHubRESTTransport:
    """Small GET-only transport. Credentials stay in request headers and never enter results."""

    def __init__(self, token: str | None = None, *, api_base: str = "https://api.github.com", timeout: float = 15.0) -> None:
        self._token = token
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout

    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        query = urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = f"{self._api_base}/{path.lstrip('/')}" + (f"?{query}" if query else "")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "office-auto-lab-editorial",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            with urlopen(Request(url, headers=headers, method="GET"), timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            kind = "inaccessible" if exc.code in {401, 403, 404} else "http_error"
            raise GitHubHTTPError(exc.code, kind) from None
        except (URLError, TimeoutError):
            raise GitHubHTTPError(None, "transport_error") from None


@dataclass(frozen=True)
class RetrievalFailure:
    source_ref: str
    failure_kind: str
    status: str = "unknown"

    def to_dict(self) -> dict[str, str]:
        return {
            "source_ref": self.source_ref,
            "failure_kind": self.failure_kind,
            "status": self.status,
        }


@dataclass(frozen=True)
class RepositoryRetrieval:
    repository_ref: str
    evidence: tuple[ActivityEvidence, ...]
    inventory: tuple[Mapping[str, Any], ...]
    failures: tuple[RetrievalFailure, ...]
    scope_status: str

    def retrieval_section(self, *, since: str, until: str) -> dict[str, Any]:
        return {
            "intended_sources": [item["source"] for item in self.inventory],
            "actual_sources": [
                item["source"] for item in self.inventory if item.get("status") == "reached"
            ],
            "time_windows": [
                {"scope": self.repository_ref, "since": since, "until": until}
            ],
            "failures": [item.to_dict() for item in self.failures],
            "scope_status": self.scope_status,
        }


def _iso(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"GitHub {label} must be present")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"GitHub {label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"GitHub {label} must include timezone")
    return value


def _observed(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, *, visibility: str, fallback: str) -> str:
    if visibility != "public":
        return fallback
    if not isinstance(value, str) or not value.strip():
        return fallback
    return " ".join(value.strip().split())[:500]


def _eligibility(visibility: str) -> str:
    if visibility == "public":
        return "eligible"
    if visibility in {"private", "internal"}:
        return "restricted"
    return "unknown"


def _visibility(repo: Mapping[str, Any]) -> str:
    value = repo.get("visibility")
    if value in {"public", "private", "internal"}:
        return str(value)
    if repo.get("private") is True:
        return "private"
    return "unknown"


def normalize_pull_request(
    repository_ref: str,
    raw: Mapping[str, Any],
    *,
    visibility: str,
    observed_at: str | None = None,
) -> ActivityEvidence:
    number = raw.get("number")
    if not isinstance(number, int):
        raise ContractError("GitHub PR number is required")
    state = raw.get("state")
    merged_at = raw.get("merged_at")
    merge_sha = raw.get("merge_commit_sha")
    merged = (
        state == "closed"
        and isinstance(merged_at, str)
        and bool(merged_at)
        and isinstance(merge_sha, str)
        and bool(merge_sha)
    )
    status = "merged" if merged else ("in_progress" if state == "open" else "unknown")
    event_at = _iso(
        merged_at if merged else raw.get("updated_at") or raw.get("created_at"),
        "PR event time",
    )
    html_url = raw.get("html_url") or f"https://github.com/{repository_ref}/pull/{number}"
    evidence_id = (
        f"github:{repository_ref}:pr:{number}:merge:{merge_sha}"
        if merged
        else f"github:{repository_ref}:pr:{number}:state:{status}"
    )
    return ActivityEvidence(
        evidence_id=evidence_id,
        source_kind="github_pr",
        source_ref=str(html_url),
        observed_at=_observed(observed_at),
        event_at=event_at,
        status=status,
        title=_safe_text(
            raw.get("title"),
            visibility=visibility,
            fallback=f"GitHub PR #{number}",
        ),
        summary=_safe_text(
            raw.get("title"),
            visibility=visibility,
            fallback=f"GitHub PR #{number} ({status})",
        ),
        repository_ref=repository_ref,
        visibility=visibility,
        public_eligibility=_eligibility(visibility),
        artifact_refs=tuple(
            [str(html_url)]
            + (
                [f"https://github.com/{repository_ref}/commit/{merge_sha}"]
                if merged
                else []
            )
        ),
        source_metadata={
            "repository": repository_ref,
            "number": number,
            "github_state": state,
            "merge_sha": merge_sha if merged else None,
            "merged_at": merged_at if merged else None,
            "url": str(html_url),
        },
    )


def normalize_release(
    repository_ref: str,
    raw: Mapping[str, Any],
    *,
    visibility: str,
    observed_at: str | None = None,
) -> ActivityEvidence:
    tag = raw.get("tag_name")
    if not isinstance(tag, str) or not tag:
        raise ContractError("GitHub release tag_name is required")
    published_at = raw.get("published_at")
    released = raw.get("draft") is not True and isinstance(published_at, str) and bool(published_at)
    status = "released" if released else "in_progress"
    event_at = _iso(
        published_at if released else raw.get("created_at"),
        "release event time",
    )
    html_url = raw.get("html_url") or f"https://github.com/{repository_ref}/releases/tag/{tag}"
    return ActivityEvidence(
        evidence_id=f"github:{repository_ref}:release:{tag}",
        source_kind="github_release",
        source_ref=str(html_url),
        observed_at=_observed(observed_at),
        event_at=event_at,
        status=status,
        title=_safe_text(
            raw.get("name") or tag,
            visibility=visibility,
            fallback=f"GitHub release {tag}",
        ),
        summary=_safe_text(
            raw.get("name") or tag,
            visibility=visibility,
            fallback=f"GitHub release {tag} ({status})",
        ),
        repository_ref=repository_ref,
        visibility=visibility,
        public_eligibility=_eligibility(visibility),
        artifact_refs=(str(html_url),),
        source_metadata={
            "repository": repository_ref,
            "tag": tag,
            "published_at": published_at if released else None,
            "draft": bool(raw.get("draft")),
            "url": str(html_url),
        },
    )


def normalize_commit(
    repository_ref: str,
    raw: Mapping[str, Any],
    *,
    visibility: str,
    observed_at: str | None = None,
) -> ActivityEvidence:
    sha = raw.get("sha")
    if not isinstance(sha, str) or not sha:
        raise ContractError("GitHub commit SHA is required")
    commit = raw.get("commit") if isinstance(raw.get("commit"), Mapping) else {}
    committer = commit.get("committer") if isinstance(commit.get("committer"), Mapping) else {}
    author = commit.get("author") if isinstance(commit.get("author"), Mapping) else {}
    event_at = _iso(
        committer.get("date") or author.get("date"),
        "commit event time",
    )
    html_url = raw.get("html_url") or f"https://github.com/{repository_ref}/commit/{sha}"
    message = commit.get("message")
    title = (
        message.splitlines()[0]
        if isinstance(message, str) and message
        else f"GitHub commit {sha[:12]}"
    )
    return ActivityEvidence(
        evidence_id=f"github:{repository_ref}:commit:{sha}",
        source_kind="github_commit",
        source_ref=str(html_url),
        observed_at=_observed(observed_at),
        event_at=event_at,
        status="completed",
        title=_safe_text(
            title,
            visibility=visibility,
            fallback=f"GitHub commit {sha[:12]}",
        ),
        summary=_safe_text(
            title,
            visibility=visibility,
            fallback=f"GitHub commit {sha[:12]}",
        ),
        repository_ref=repository_ref,
        visibility=visibility,
        public_eligibility=_eligibility(visibility),
        artifact_refs=(str(html_url),),
        source_metadata={
            "repository": repository_ref,
            "sha": sha,
            "url": str(html_url),
        },
    )


_DECISION_LABELS = {
    "waiting": "waiting",
    "status:waiting": "waiting",
    "status: waiting": "waiting",
    "status/waiting": "waiting",
    "decision:waiting": "waiting",
    "drop": "dropped",
    "dropped": "dropped",
    "status:dropped": "dropped",
    "status:drop": "dropped",
    "decision:drop": "dropped",
    "done": "completed",
    "completed": "completed",
    "status:completed": "completed",
    "status/done": "completed",
    "decision:completed": "completed",
    "failed": "failed",
    "status:failed": "failed",
    "decision:failed": "failed",
    "superseded": "superseded",
    "status:superseded": "superseded",
    "decision:superseded": "superseded",
}


def normalize_issue_decision(
    repository_ref: str,
    raw: Mapping[str, Any],
    *,
    visibility: str,
    observed_at: str | None = None,
) -> ActivityEvidence | None:
    number = raw.get("number")
    if not isinstance(number, int):
        raise ContractError("GitHub issue number is required")
    labels = raw.get("labels") if isinstance(raw.get("labels"), list) else []
    names: list[str] = []
    for label in labels:
        if isinstance(label, str):
            names.append(label.lower())
        elif isinstance(label, Mapping) and isinstance(label.get("name"), str):
            names.append(label["name"].lower())
    statuses = sorted({_DECISION_LABELS[name] for name in names if name in _DECISION_LABELS})
    if not statuses:
        return None
    if len(statuses) != 1:
        raise ContractError(f"issue #{number} has conflicting explicit editorial status labels")
    status = statuses[0]
    event_at = _iso(
        raw.get("updated_at") or raw.get("closed_at") or raw.get("created_at"),
        "issue decision time",
    )
    html_url = raw.get("html_url") or f"https://github.com/{repository_ref}/issues/{number}"
    return ActivityEvidence(
        evidence_id=f"github:{repository_ref}:issue:{number}:decision:{status}",
        source_kind="github_issue_decision",
        source_ref=str(html_url),
        observed_at=_observed(observed_at),
        event_at=event_at,
        status=status,
        title=_safe_text(
            raw.get("title"),
            visibility=visibility,
            fallback=f"GitHub issue #{number}",
        ),
        summary=_safe_text(
            raw.get("title"),
            visibility=visibility,
            fallback=f"GitHub issue #{number} ({status})",
        ),
        repository_ref=repository_ref,
        visibility=visibility,
        public_eligibility=_eligibility(visibility),
        artifact_refs=(str(html_url),),
        source_metadata={
            "repository": repository_ref,
            "issue_number": number,
            "decision_status": status,
            "url": str(html_url),
        },
    )


def dedupe_evidence(items: Sequence[ActivityEvidence]) -> tuple[ActivityEvidence, ...]:
    by_id: dict[str, ActivityEvidence] = {}
    for item in items:
        previous = by_id.get(item.evidence_id)
        if previous is None:
            by_id[item.evidence_id] = item
            continue
        left, right = previous.to_dict(), item.to_dict()
        left.pop("observed_at", None)
        right.pop("observed_at", None)
        if left != right:
            raise ContractError(f"stable evidence ID collision for {item.evidence_id}")
        if item.observed_at < previous.observed_at:
            by_id[item.evidence_id] = item
    return tuple(by_id[key] for key in sorted(by_id))


class GitHubEvidenceClient:
    def __init__(self, transport: GitHubTransport) -> None:
        self.transport = transport

    def list_owned_repositories(
        self,
        *,
        owner: str,
        include_archived: bool = False,
        max_pages: int = 10,
    ) -> tuple[str, ...]:
        if not owner or "/" in owner:
            raise ContractError("GitHub owner must be one account login")
        if not 1 <= max_pages <= 20:
            raise ContractError("max_pages must be between 1 and 20")
        repositories: list[str] = []
        for page in range(1, max_pages + 1):
            rows = _list_of_mappings(
                self.transport.get_json(
                    "user/repos",
                    {
                        "affiliation": "owner",
                        "visibility": "all",
                        "sort": "full_name",
                        "direction": "asc",
                        "per_page": 100,
                        "page": page,
                    },
                ),
                "owned repository list",
            )
            for raw in rows:
                full_name = raw.get("full_name")
                raw_owner = raw.get("owner") if isinstance(raw.get("owner"), Mapping) else {}
                if raw_owner.get("login") != owner:
                    continue
                if raw.get("disabled") is True:
                    continue
                if not include_archived and raw.get("archived") is True:
                    continue
                if isinstance(full_name, str) and full_name:
                    repositories.append(full_name)
            if len(rows) < 100:
                break
        else:
            raise ContractError("owned repository discovery exceeded max_pages")
        return tuple(sorted(set(repositories)))

    def fetch_pull_request(
        self,
        repository_ref: str,
        number: int,
        *,
        observed_at: str | None = None,
    ) -> ActivityEvidence:
        repo = self.transport.get_json(f"repos/{repository_ref}")
        visibility = _visibility(_mapping(repo, "repository response"))
        raw = self.transport.get_json(f"repos/{repository_ref}/pulls/{number}")
        return normalize_pull_request(
            repository_ref,
            _mapping(raw, "pull request response"),
            visibility=visibility,
            observed_at=observed_at,
        )

    def retrieve_repository_activity(
        self,
        repository_ref: str,
        *,
        since: str,
        until: str,
        kinds: Sequence[str] = (
            "github_pr",
            "github_release",
            "github_commit",
            "github_issue_decision",
        ),
        max_per_kind: int = 50,
        observed_at: str | None = None,
    ) -> RepositoryRetrieval:
        if not 1 <= max_per_kind <= 100:
            raise ContractError("max_per_kind must be between 1 and 100")
        wanted = tuple(dict.fromkeys(kinds))
        supported = {"github_pr", "github_release", "github_commit", "github_issue_decision"}
        unsupported = set(wanted) - supported
        if unsupported:
            raise ContractError(f"unsupported GitHub evidence kinds: {sorted(unsupported)}")
        start, end = _parse_window(since, until)
        inventory = tuple(
            {"source": kind, "status": "unknown", "count": 0}
            for kind in wanted
        )
        failures: list[RetrievalFailure] = []
        try:
            repo = _mapping(
                self.transport.get_json(f"repos/{repository_ref}"),
                "repository response",
            )
            visibility = _visibility(repo)
        except GitHubHTTPError as exc:
            failures.append(RetrievalFailure(repository_ref, exc.failure_kind))
            return RepositoryRetrieval(
                repository_ref,
                (),
                inventory,
                tuple(failures),
                "unknown",
            )

        inventory_work = [dict(item) for item in inventory]
        items: list[ActivityEvidence] = []
        for index, kind in enumerate(wanted):
            try:
                rows = self._retrieve_kind(
                    repository_ref,
                    kind,
                    max_per_kind=max_per_kind,
                    visibility=visibility,
                    observed_at=observed_at,
                    start=start,
                    end=end,
                )
                filtered = [
                    item
                    for item in rows
                    if start <= _parse_time(item.event_at) <= end
                ]
                items.extend(filtered)
                inventory_work[index] = {
                    "source": kind,
                    "status": "reached",
                    "count": len(filtered),
                }
            except GitHubHTTPError as exc:
                failures.append(
                    RetrievalFailure(f"{repository_ref}:{kind}", exc.failure_kind)
                )
                inventory_work[index] = {
                    "source": kind,
                    "status": "unknown",
                    "count": 0,
                }
        scope = "complete" if not failures else "degraded"
        return RepositoryRetrieval(
            repository_ref,
            dedupe_evidence(items),
            tuple(inventory_work),
            tuple(failures),
            scope,
        )

    def _retrieve_kind(
        self,
        repo: str,
        kind: str,
        *,
        max_per_kind: int,
        visibility: str,
        observed_at: str | None,
        start: datetime,
        end: datetime,
    ) -> list[ActivityEvidence]:
        if kind == "github_pr":
            listed = self.transport.get_json(
                f"repos/{repo}/pulls",
                {
                    "state": "closed",
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": max_per_kind,
                },
            )
            rows: list[ActivityEvidence] = []
            for raw in _list_of_mappings(listed, "pull list"):
                updated_at = raw.get("updated_at")
                if not isinstance(updated_at, str):
                    continue
                updated = _parse_time(updated_at)
                if updated < start:
                    break
                if updated > end:
                    continue
                number = raw.get("number")
                if not isinstance(number, int):
                    continue
                detail = _mapping(
                    self.transport.get_json(f"repos/{repo}/pulls/{number}"),
                    "pull response",
                )
                item = normalize_pull_request(
                    repo,
                    detail,
                    visibility=visibility,
                    observed_at=observed_at,
                )
                if item.status == "merged":
                    rows.append(item)
            return rows
        if kind == "github_release":
            return [
                normalize_release(
                    repo,
                    raw,
                    visibility=visibility,
                    observed_at=observed_at,
                )
                for raw in _list_of_mappings(
                    self.transport.get_json(
                        f"repos/{repo}/releases",
                        {"per_page": max_per_kind},
                    ),
                    "release list",
                )
            ]
        if kind == "github_commit":
            return [
                normalize_commit(
                    repo,
                    raw,
                    visibility=visibility,
                    observed_at=observed_at,
                )
                for raw in _list_of_mappings(
                    self.transport.get_json(
                        f"repos/{repo}/commits",
                        {
                            "per_page": max_per_kind,
                            "since": start.isoformat().replace("+00:00", "Z"),
                            "until": end.isoformat().replace("+00:00", "Z"),
                        },
                    ),
                    "commit list",
                )
            ]
        rows = []
        for raw in _list_of_mappings(
            self.transport.get_json(
                f"repos/{repo}/issues",
                {
                    "state": "all",
                    "sort": "updated",
                    "direction": "desc",
                    "since": start.isoformat().replace("+00:00", "Z"),
                    "per_page": max_per_kind,
                },
            ),
            "issue list",
        ):
            if "pull_request" in raw:
                continue
            item = normalize_issue_decision(
                repo,
                raw,
                visibility=visibility,
                observed_at=observed_at,
            )
            if item:
                rows.append(item)
        return rows


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{label} must be an object")
    return value


def _list_of_mappings(value: Any, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise ContractError(f"{label} must be an array")
    return [item for item in value if isinstance(item, Mapping)]


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ContractError("GitHub retrieval timestamps must be timezone-aware")
    return parsed


def _parse_window(since: str, until: str) -> tuple[datetime, datetime]:
    start, end = _parse_time(since), _parse_time(until)
    if start > end:
        raise ContractError("GitHub retrieval window since must not be after until")
    return start, end
