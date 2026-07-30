from __future__ import annotations

import base64
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, Mapping, Protocol, Sequence

import requests

_REPOSITORY_ID = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class RepositorySourceError(RuntimeError):
    """Bounded source error with a stable machine category."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class RepositoryFacts:
    full_name: str
    default_branch: str
    head_sha: str
    archived: bool = False
    private: bool = False


@dataclass(frozen=True)
class CommitFacts:
    sha: str
    committed_at: datetime
    subject: str


@dataclass(frozen=True)
class TreeEntry:
    path: str
    kind: str
    size: int | None = None


class RepositorySource(Protocol):
    def get_repository(self, repository_full_name: str) -> RepositoryFacts: ...
    def list_tree(self, repository_full_name: str, ref: str) -> list[TreeEntry]: ...
    def read_text(self, repository_full_name: str, path: str, ref: str) -> str: ...
    def list_commits(self, repository_full_name: str, *, since: datetime) -> list[CommitFacts]: ...


def validate_repository_identity(repository_full_name: str, allowlist: Iterable[str]) -> str:
    identity = str(repository_full_name or "").strip()
    if not _REPOSITORY_ID.fullmatch(identity) or ".." in identity:
        raise RepositorySourceError("invalid_identity", "repository identity must be owner/repository")
    if identity not in set(allowlist):
        raise RepositorySourceError("not_allowlisted", f"repository {identity!r} is not allowlisted")
    return identity


class GitHubRepositorySource:
    """Read-only, allowlisted GitHub REST adapter with bounded responses."""

    def __init__(
        self,
        allowlist: Iterable[str],
        *,
        token: str | None = None,
        session: requests.Session | None = None,
        api_root: str = "https://api.github.com",
        timeout_s: float = 10.0,
        max_tree_entries: int = 2000,
    ) -> None:
        self.allowlist = frozenset(allowlist)
        self.session = session or requests.Session()
        self.api_root = api_root.rstrip("/")
        self.timeout_s = timeout_s
        self.max_tree_entries = max_tree_entries
        self.headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _get(self, identity: str, suffix: str, *, params: Mapping[str, object] | None = None) -> object:
        identity = validate_repository_identity(identity, self.allowlist)
        try:
            response = self.session.get(
                f"{self.api_root}/repos/{identity}{suffix}",
                headers=self.headers,
                params=dict(params or {}),
                timeout=self.timeout_s,
            )
        except requests.RequestException as exc:
            raise RepositorySourceError("transport_error", "GitHub read transport failed") from exc
        if response.status_code == 404:
            raise RepositorySourceError("not_found", f"repository resource not found: {suffix or '/'}")
        if response.status_code in {401, 403}:
            category = "rate_limited" if response.headers.get("X-RateLimit-Remaining") == "0" else "forbidden"
            raise RepositorySourceError(category, f"GitHub read denied with HTTP {response.status_code}")
        if response.status_code >= 400:
            raise RepositorySourceError("http_error", f"GitHub read failed with HTTP {response.status_code}")
        return response.json()

    def get_repository(self, repository_full_name: str) -> RepositoryFacts:
        data = self._get(repository_full_name, "")
        if not isinstance(data, dict):
            raise RepositorySourceError("invalid_response", "repository response is not an object")
        branch = str(data.get("default_branch") or "")
        commit = self._get(repository_full_name, f"/commits/{branch}")
        if not isinstance(commit, dict):
            raise RepositorySourceError("invalid_response", "head commit response is not an object")
        return RepositoryFacts(
            full_name=str(data.get("full_name") or repository_full_name),
            default_branch=branch,
            head_sha=str(commit.get("sha") or ""),
            archived=bool(data.get("archived")),
            private=bool(data.get("private")),
        )

    def list_tree(self, repository_full_name: str, ref: str) -> list[TreeEntry]:
        data = self._get(repository_full_name, f"/git/trees/{ref}", params={"recursive": "1"})
        if not isinstance(data, dict):
            raise RepositorySourceError("invalid_response", "tree response is not an object")
        raw = data.get("tree") or []
        if data.get("truncated") or len(raw) > self.max_tree_entries:
            raise RepositorySourceError("tree_too_large", "repository tree exceeds bounded inspection limit")
        return [TreeEntry(str(item["path"]), str(item.get("type") or ""), item.get("size")) for item in raw]

    def read_text(self, repository_full_name: str, path: str, ref: str) -> str:
        safe_path = str(PurePosixPath(path))
        if safe_path.startswith("../") or safe_path.startswith("/"):
            raise RepositorySourceError("invalid_path", "repository path must be relative")
        data = self._get(repository_full_name, f"/contents/{safe_path}", params={"ref": ref})
        if not isinstance(data, dict):
            raise RepositorySourceError("invalid_response", "content response is not an object")
        if data.get("encoding") != "base64":
            raise RepositorySourceError("unsupported_content", "GitHub content is not base64 text")
        raw = base64.b64decode(str(data.get("content") or ""), validate=False)
        if len(raw) > 100_000 or b"\0" in raw[:8000]:
            raise RepositorySourceError("unsupported_content", "content is too large or binary")
        return raw.decode("utf-8", errors="replace")

    def list_commits(self, repository_full_name: str, *, since: datetime) -> list[CommitFacts]:
        data = self._get(repository_full_name, "/commits", params={"since": since.astimezone(timezone.utc).isoformat(), "per_page": 100})
        if not isinstance(data, list):
            raise RepositorySourceError("invalid_response", "commit response is not a list")
        commits: list[CommitFacts] = []
        for item in data[:100]:
            commit = item.get("commit") or {}
            author = commit.get("author") or {}
            committed_at = datetime.fromisoformat(str(author["date"]).replace("Z", "+00:00"))
            commits.append(CommitFacts(str(item.get("sha") or ""), committed_at, str(commit.get("message") or "").splitlines()[0][:200]))
        return commits


class LocalRepositorySource:
    """Local compatibility adapter for source facts supported by remote inspection."""

    def __init__(self, repositories: Mapping[str, str]) -> None:
        self.repositories = {name: str(Path(path).resolve()) for name, path in repositories.items()}

    def _root(self, identity: str) -> str:
        validate_repository_identity(identity, self.repositories)
        root = self.repositories[identity]
        if not os.path.isdir(root):
            raise RepositorySourceError("not_found", f"local repository {identity!r} is missing")
        return root

    def _git(self, identity: str, *args: str) -> str:
        completed = subprocess.run(["git", *args], cwd=self._root(identity), text=True, capture_output=True, timeout=5)
        if completed.returncode:
            raise RepositorySourceError("git_error", completed.stderr.strip()[:200])
        return completed.stdout.strip()

    def get_repository(self, repository_full_name: str) -> RepositoryFacts:
        branch = self._git(repository_full_name, "rev-parse", "--abbrev-ref", "HEAD")
        sha = self._git(repository_full_name, "rev-parse", "HEAD")
        return RepositoryFacts(repository_full_name, branch, sha)

    def list_tree(self, repository_full_name: str, ref: str) -> list[TreeEntry]:
        rows = self._git(repository_full_name, "ls-tree", "-r", "-l", ref).splitlines()
        entries = []
        for row in rows:
            meta, path = row.split("\t", 1)
            _mode, kind, _sha, size = meta.split()
            entries.append(TreeEntry(path, kind, None if size == "-" else int(size)))
        return entries

    def read_text(self, repository_full_name: str, path: str, ref: str) -> str:
        return self._git(repository_full_name, "show", f"{ref}:{path}")

    def list_commits(self, repository_full_name: str, *, since: datetime) -> list[CommitFacts]:
        fmt = "%H%x1f%cI%x1f%s"
        rows = self._git(repository_full_name, "log", f"--since={since.astimezone(timezone.utc).isoformat()}", f"--format={fmt}").splitlines()
        return [CommitFacts(sha, datetime.fromisoformat(ts), subject) for sha, ts, subject in (row.split("\x1f", 2) for row in rows if row)]


class InMemoryRepositorySource:
    """Deterministic fake used by plugin and orchestration tests."""

    def __init__(self, facts: RepositoryFacts, entries: Sequence[TreeEntry], files: Mapping[str, str], commits: Sequence[CommitFacts]) -> None:
        self.facts, self.entries, self.files, self.commits = facts, list(entries), dict(files), list(commits)

    def get_repository(self, repository_full_name: str) -> RepositoryFacts:
        if repository_full_name != self.facts.full_name:
            raise RepositorySourceError("not_found", repository_full_name)
        return self.facts

    def list_tree(self, repository_full_name: str, ref: str) -> list[TreeEntry]:
        self.get_repository(repository_full_name)
        return list(self.entries)

    def read_text(self, repository_full_name: str, path: str, ref: str) -> str:
        self.get_repository(repository_full_name)
        return self.files[path]

    def list_commits(self, repository_full_name: str, *, since: datetime) -> list[CommitFacts]:
        self.get_repository(repository_full_name)
        return [commit for commit in self.commits if commit.committed_at >= since]
