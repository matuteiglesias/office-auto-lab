from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .contracts import ContractError, PolicyIdentity


@dataclass(frozen=True)
class ContextDocument:
    context_id: str
    repository_path: str
    content_sha256: str
    text: str

    def provenance(self) -> dict[str, str]:
        return {
            "context_id": self.context_id,
            "repository_path": self.repository_path,
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True)
class PinnedPolicy:
    identity: PolicyIdentity
    text: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_repository_context(repo_root: str | Path, paths: Iterable[str | Path]) -> tuple[ContextDocument, ...]:
    root = Path(repo_root).resolve()
    documents: list[ContextDocument] = []
    for requested in paths:
        relative = _safe_relative_path(requested)
        resolved = (root / relative).resolve()
        if root != resolved and root not in resolved.parents:
            raise ContractError(f"context path escapes repository root: {relative.as_posix()}")
        if not resolved.is_file():
            raise ContractError(f"context file does not exist: {relative.as_posix()}")
        text = resolved.read_text(encoding="utf-8")
        digest = sha256_text(text)
        repository_path = relative.as_posix()
        documents.append(
            ContextDocument(
                context_id=f"repo-context:sha256:{digest}",
                repository_path=repository_path,
                content_sha256=digest,
                text=text,
            )
        )
    return tuple(documents)


def load_pinned_policy_file(
    repo_root: str | Path,
    relative_path: str | Path,
    *,
    authority: str,
    source_ref: str,
    source_revision: str,
    expected_sha256: str,
) -> PinnedPolicy:
    document = load_repository_context(repo_root, [relative_path])[0]
    expected = expected_sha256.strip().lower()
    if document.content_sha256 != expected:
        raise ContractError(
            "pinned editorial policy hash mismatch; refusing moving or stale policy content"
        )
    identity = PolicyIdentity.from_mapping(
        {
            "authority": authority,
            "source_ref": source_ref,
            "source_revision": source_revision,
            "content_sha256": document.content_sha256,
        }
    )
    return PinnedPolicy(identity=identity, text=document.text)


def pin_policy_text(
    text: str,
    *,
    authority: str,
    source_ref: str,
    source_revision: str,
    expected_sha256: str,
) -> PinnedPolicy:
    digest = sha256_text(text)
    if digest != expected_sha256.strip().lower():
        raise ContractError("pinned editorial policy hash mismatch")
    identity = PolicyIdentity.from_mapping(
        {
            "authority": authority,
            "source_ref": source_ref,
            "source_revision": source_revision,
            "content_sha256": digest,
        }
    )
    return PinnedPolicy(identity=identity, text=text)


def _safe_relative_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ContractError("repository context paths must be repository-relative")
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ContractError("repository context paths must not contain traversal segments")
    return path
