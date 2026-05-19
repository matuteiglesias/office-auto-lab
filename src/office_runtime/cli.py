from __future__ import annotations
import json
from office_runtime.office.config import load_config
from office_runtime.office.compile import run_compile
from office_runtime.staff.bundles import build_bundles
from office_runtime.staff.briefs import build_staff_briefs

def main() -> int:
    cfg = load_config()
    manifest = run_compile(cfg)
    if manifest.get("status") == "ok":
        manifest["bundle_build"] = build_bundles(cfg)
        manifest["brief_build"] = build_staff_briefs(cfg.latest_dir)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest.get("status") == "ok" else 1

if __name__ == "__main__":
    raise SystemExit(main())
