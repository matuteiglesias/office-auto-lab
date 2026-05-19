.PHONY: smoke imports repo-scans compile-blocks office audit

smoke: imports repo-scans compile-blocks

imports:
	PYTHONPATH=src python3 -c "import office.main; import office.compile; import office.bundles; import office.staff_briefs; import repo_health.policy; import repo_health.sheets; import repo_health.frontier_export; import repo_health.run_frontier; import repo_health.compiler.generate; import repo_health.compiler.ir; import repo_health.compiler.classify; import repo_health.plugins.base; import repo_health.plugins.runbook_plugin; import repo_health.plugins.smoke_plugin; import repo_health.plugins.commit_recent_plugin; import repo_health.plugins.env_plugin; import repo_health.plugins.pipeline_output_plugin; from repo_health.plugin_loader import load_plugins_from_folder; plugins = load_plugins_from_folder(); print('plugins:', sorted(plugins)); print('imports ok')"

repo-scans:
	bash scripts/repo_prereqs_scan.sh "$$PWD" >/tmp/office_auto_lab_prereqs.tsv
	bash scripts/repo_srp.sh "$$PWD" >/tmp/office_auto_lab_srp.txt
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
	PYTHONPATH=src python3 -m office.main

audit:
	rg -n "^\s*from\s+(sheets|policy|utils|utils_frontier_export|compiler|plugins)\b|^\s*import\s+(sheets|policy|utils|utils_frontier_export|compiler|plugins)\b" src scripts || true
