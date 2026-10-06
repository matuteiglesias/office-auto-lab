from .github import (
    GitHubEvidenceClient,
    GitHubHTTPError,
    GitHubRESTTransport,
    RepositoryRetrieval,
    RetrievalFailure,
    dedupe_evidence,
    normalize_commit,
    normalize_issue_decision,
    normalize_pull_request,
    normalize_release,
)

__all__ = [
    "GitHubEvidenceClient", "GitHubHTTPError", "GitHubRESTTransport",
    "RepositoryRetrieval", "RetrievalFailure", "dedupe_evidence",
    "normalize_commit", "normalize_issue_decision", "normalize_pull_request", "normalize_release",
]
