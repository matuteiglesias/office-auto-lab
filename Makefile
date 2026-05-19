.PHONY: smoke imports repo-scans compile-blocks office audit

smoke: imports repo-scans compile-blocks

imports:
	PYTHONPATH=src python3 - <<'PY'
	import office_runtime
	import office_runtime.cli

	import office_runtime.office.compile
	import office_runtime.office.config
	import office_runtime.office.io
	import office_runtime.office.render
	import office_runtime.office.validate

	import office_runtime.staff.bundles
	import office_runtime.staff.briefs

	import office_runtime.ops.repo_health.policy
	import office_runtime.ops.repo_health.sheets
	import office_runtime.ops.repo_health.frontier_export
	import office_runtime.ops.repo_health.runner
	import office_runtime.ops.repo_health.plugin_loader

	import office_runtime.ops.repo_health.compiler.generate
	import office_runtime.ops.repo_health.compiler.ir
	import office_runtime.ops.repo_health.compiler.classify

	import office_runtime.ops.repo_health.plugins.base
	import office_runtime.ops.repo_health.plugins.git_activity_plugin
	import office_runtime.ops.repo_health.plugins.make_smoke_plugin
	import office_runtime.ops.repo_health.plugins.repo_artifact_plugin
	import office_runtime.ops.repo_health.plugins.repo_env_plugin
	import office_runtime.ops.repo_health.plugins.repo_runbook_plugin

	from office_runtime.ops.repo_health.plugin_loader import load_plugins_from_folder
	plugins = load_plugins_from_folder("src/office_runtime/ops/repo_health/plugins")
	print("plugins:", sorted(plugins))
	print("imports ok")
	PY
	
repo-scans:
	bash scripts/repo_contract_scan.sh "$$PWD" >/tmp/office_auto_lab_prereqs.tsv
	bash scripts/repo_snapshot_protocol.sh "$$PWD" >/tmp/office_auto_lab_srp.txt
	test -s /tmp/office_auto_lab_prereqs.tsv
	test -s /tmp/office_auto_lab_srp.txt
	@echo "repo scans ok"

compile-blocks:
	mkdir -p out/frontier
	cp fixtures/frontier_sample_v2.csv out/frontier/latest.csv 2>/dev/null || cp fixtures/frontier_sample.csv out/frontier/latest.csv
	PYTHONPATH=src python3 scripts/compile_blocks.py --frontier out/frontier/latest.csv --date "$$(date +%F)"
	test -s out/compiler/$$(date +%F)/prepared_blocks.jsonl
	@echo "compile blocks ok"

office:
	PYTHONPATH=src python3 -m office_runtime.office.main

audit:
	rg -n "^\s*from\s+(sheets|policy|utils|utils_frontier_export|compiler|plugins)\b|^\s*import\s+(sheets|policy|utils|utils_frontier_export|compiler|plugins)\b" src scripts || true
