from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from office_runtime.ops.repo_health.sheets import auth_gspread, read_tab_records


PROJECTS = "front_registry"
CAPABILITIES = "Capabilities"
PLUGIN_POLICY = "PluginPolicy"
PLUGIN_PREREQS = "PluginPrereqs"


def s(x) -> str:
    return "" if x is None else str(x).strip()


def boolish(x) -> bool:
    return s(x).lower() in {"1", "true", "yes", "y", "x", "on"}


def header(rows):
    if not rows:
        return []
    keys = set()
    for r in rows[:20]:
        keys.update(r.keys())
    return sorted(keys)


def count_blank(rows, col):
    return sum(1 for r in rows if not s(r.get(col)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet-id", required=True)
    ap.add_argument("--sa", required=True)
    args = ap.parse_args()

    gc = auth_gspread(args.sa)
    sh = gc.open_by_key(args.sheet_id)

    projects = read_tab_records(sh, PROJECTS)
    capabilities = read_tab_records(sh, CAPABILITIES)
    policy = read_tab_records(sh, PLUGIN_POLICY)
    prereqs = read_tab_records(sh, PLUGIN_PREREQS)

    issues = []

    print("# Sheet Doctor")
    print()
    print("## Row counts")
    for name, rows in [
        (PROJECTS, projects),
        (CAPABILITIES, capabilities),
        (PLUGIN_POLICY, policy),
        (PLUGIN_PREREQS, prereqs),
    ]:
        print(f"- {name}: {len(rows)} rows")
    print()

    # Projects
    print("## Projects")
    pids = [s(r.get("project_id")) for r in projects if s(r.get("project_id"))]
    dup_pids = [pid for pid, n in Counter(pids).items() if n > 1]
    print(f"- indexed project_id: {len(set(pids))}")
    print(f"- blank project_id rows: {count_blank(projects, 'project_id')}")
    print(f"- duplicate project_id: {len(dup_pids)}")
    if dup_pids:
        print(f"  - examples: {dup_pids[:20]}")

    for col in ["Title", "Priority", "repo_path", "workdir", "next", "enabled"]:
        if col in header(projects):
            print(f"- blank {col}: {count_blank(projects, col)}")

    # Capabilities
    print()
    print("## Capabilities")
    cap_header = header(capabilities)
    wide_cap_cols = [c for c in cap_header if c.startswith("cap_")]
    tall = "capability_tag" in cap_header
    print(f"- mode: {'tall' if tall else 'wide' if wide_cap_cols else 'unknown'}")
    print(f"- wide cap_* cols: {len(wide_cap_cols)}")
    print(f"- blank project_id rows: {count_blank(capabilities, 'project_id')}")

    cap_pids = {s(r.get("project_id")) for r in capabilities if s(r.get("project_id"))}
    missing_project_rows = sorted(cap_pids - set(pids))
    print(f"- capability pids not in Projects: {len(missing_project_rows)}")
    if missing_project_rows:
        print(f"  - examples: {missing_project_rows[:20]}")

    projects_without_caps = sorted(set(pids) - cap_pids)
    print(f"- Projects without capability row: {len(projects_without_caps)}")
    if projects_without_caps:
        print(f"  - examples: {projects_without_caps[:30]}")

    # PluginPolicy
    print()
    print("## PluginPolicy")
    print(f"- blank capability_tag/capability: {sum(1 for r in policy if not (s(r.get('capability_tag')) or s(r.get('capability'))))}")
    print(f"- blank plugin: {count_blank(policy, 'plugin')}")
    plugins_from_policy = {s(r.get("plugin")) for r in policy if s(r.get("plugin"))}
    print(f"- plugins in policy: {sorted(plugins_from_policy)}")

    # PluginPrereqs
    print()
    print("## PluginPrereqs")
    print(f"- blank plugin: {count_blank(prereqs, 'plugin')}")
    plugins_from_prereqs = {s(r.get("plugin")) for r in prereqs if s(r.get("plugin"))}
    print(f"- plugins in prereqs: {sorted(plugins_from_prereqs)}")

    policy_without_prereqs = sorted(plugins_from_policy - plugins_from_prereqs)
    prereqs_without_policy = sorted(plugins_from_prereqs - plugins_from_policy)
    print(f"- policy plugins without prereqs: {policy_without_prereqs}")
    print(f"- prereq plugins without policy: {prereqs_without_policy}")

    # Required field completeness, by plugin
    print()
    print("## Required field pressure")
    req_by_plugin = {}
    for r in prereqs:
        plugin = s(r.get("plugin"))
        req = s(r.get("required_fields"))
        if plugin:
            req_by_plugin[plugin] = req

    for plugin, req in sorted(req_by_plugin.items()):
        if not req:
            print(f"- {plugin}: no required_fields")
            continue
        groups = [x.strip() for x in req.split(",") if x.strip()]
        missing_counts = defaultdict(int)
        for p in projects:
            pid = s(p.get("project_id"))
            if not pid:
                continue
            for g in groups:
                alts = [a.strip() for a in g.replace("|", " OR ").split(" OR ") if a.strip()]
                if not any(s(p.get(a)) for a in alts):
                    missing_counts[g] += 1
        top = ", ".join(f"{k}={v}" for k, v in sorted(missing_counts.items(), key=lambda kv: -kv[1])[:5])
        print(f"- {plugin}: {req} | missing: {top or 'none'}")

    print()
    print("## Suggested next actions")
    print("- Fix duplicate or blank project_id first.")
    print("- Then fix capability rows missing matching Projects rows.")
    print("- Then fix policy plugins with no prereqs or unknown plugin names.")
    print("- Then reduce missing required_fields for plugins that should actually run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
