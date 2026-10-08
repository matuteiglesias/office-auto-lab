"""Rebuildable, idempotent projection of canonical observer records."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .contracts import ActivityEvent, ObservedPost


@dataclass
class MemoryProjection:
    events: dict[str, ActivityEvent] = field(default_factory=dict)
    posts: dict[str, ObservedPost] = field(default_factory=dict)
    runs: list[dict[str, object]] = field(default_factory=list)

    def apply(self, events: Iterable[ActivityEvent], posts: Iterable[ObservedPost]) -> None:
        for event in events:
            self.events.setdefault(event.event_id, event)
        for post in posts:
            existing = self.posts.get(post.post_id)
            if existing is None or existing.content_sha256 != post.content_sha256:
                self.posts[post.post_id] = post

    def add_run(self, run: dict[str, object]) -> None:
        if not any(item.get("run_id") == run.get("run_id") for item in self.runs):
            self.runs.append(dict(run))

    def snapshot(self) -> dict[str, object]:
        return {"events": [e.record() for e in self.events.values()], "posts": [p.record() for p in self.posts.values()], "runs": list(self.runs)}
