from __future__ import annotations

import argparse
import os

from office_runtime.editorial.publisher.manual_intake import GoogleManualSheet, project_manual_drafts


def main() -> int:
    parser = argparse.ArgumentParser(description="Project manual argentina_econ DRAFTS into Editorial contracts")
    parser.add_argument("--apply", action="store_true", help="write machine-owned DRAFTS/CANDIDATES/QUEUE state")
    args = parser.parse_args()
    sheet_id = os.environ.get("EDITORIAL_ARGENTINA_ECON_SHEET_ID")
    if not sheet_id:
        parser.error("EDITORIAL_ARGENTINA_ECON_SHEET_ID must be set")
    if not args.apply:
        print({"state": "DRY_RUN", "sheet_id": sheet_id, "message": "set --apply to project manual drafts"})
        return 0
    result = project_manual_drafts(GoogleManualSheet.from_environment(sheet_id))
    print({"state": "APPLIED", "staged": result.staged, "unchanged": result.unchanged, "blocked": result.blocked, "rows": result.rows})
    return 0 if result.blocked == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
