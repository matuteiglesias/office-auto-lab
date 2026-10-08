#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from office_runtime.media_evidence import CompositionError, CompositionRequest, compose_media_selection


def main() -> int:
    parser = argparse.ArgumentParser(description="Compose Media Monitor evidence into a governed KB Artifacts selection.")
    parser.add_argument("--selection-id", required=True)
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    parser.add_argument("--topic", required=True, help="Case-insensitive regex used by KB Artifacts selection.")
    parser.add_argument("--media-monitor-root", type=Path, required=True)
    parser.add_argument("--media-store-root", type=Path, required=True)
    parser.add_argument("--kb-artifacts-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, default=Path("artifacts/media-evidence-composition"))
    parser.add_argument("--apply", action="store_true", help="Execute producer export and KB selection. Without this flag only print the plan.")
    args = parser.parse_args()
    try:
        result = compose_media_selection(
            request=CompositionRequest(
                selection_id=args.selection_id,
                start=args.start,
                end=args.end,
                topic_pattern=args.topic,
            ),
            media_monitor_root=args.media_monitor_root,
            media_store_root=args.media_store_root,
            kb_artifacts_root=args.kb_artifacts_root,
            work_root=args.work_root,
            apply=args.apply,
        )
    except CompositionError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
