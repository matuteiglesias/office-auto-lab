#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from office_runtime.office.config import load_config
from office_runtime.office.frontier_view import publish_relationship_agenda_view


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile the read-only Frontier relationship-agenda view.")
    parser.add_argument("--run-id", default=default_run_id())
    parser.add_argument("--include-closed", action="store_true")
    parser.add_argument("--shadow", action="store_true", help="Write a run but do not advance current.json or export.")
    parser.add_argument(
        "--export",
        default=os.environ.get("FRONTIER_VIEW_EXPORT_PATH", "").strip(),
        help="Optional path for the renderer-facing frontier.view.v1.json copy.",
    )
    args = parser.parse_args(argv)

    result = publish_relationship_agenda_view(
        load_config(),
        run_id=args.run_id,
        include_closed=args.include_closed,
        publish=not args.shadow,
        export_path=Path(args.export).expanduser().resolve() if args.export and not args.shadow else None,
    )

    view = result["view"]
    print(
        f"frontier view {result['run_id']}: "
        f"{view['counts']['items']} items, "
        f"published={result['published']}, "
        f"digest={view['view_digest']}"
    )
    if result["export_path"]:
        print(f"exported: {result['export_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
