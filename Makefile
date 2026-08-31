.PHONY: imports docs-check parent-docs-check audit parent-audit daily office-compile staff-bundles staff-briefs capture-lifecycle repo-health-policy repo-health-run evidence-git evidence-files smoke editorial-contracts dependency-contracts systemd-contracts runtime-contracts install-profile repo-scans compile-blocks office evidence-today logs-tail

ROOTS ?= .
START ?= $(shell date +%F)
END ?= $(shell date +%F)
OUT_DIR ?= artifacts/evidence
GIT_OUT ?= $(OUT_DIR)/git_trace/$(START)_$(END).jsonl
FILES_OUT ?= $(OUT_DIR)/fs_trace/$(START)_$(END).jsonl

smoke: imports editorial-contracts runtime-contracts repo-scans compile-blocks

imports:
	PYTHONPATH=src python3 -c "import office_runtime; \
import office_runtime.cli; \
import office_runtime.capture; \
import office_runtime.capture.lifecycle; \
import office_runtime.editorial; \
import office_runtime.editorial.contracts; \
import office_runtime.office.compile; \
import office_runtime.office.config; \
import office_runtime.office.io; \
import office_runtime.office.render; \
import office_runtime.office.validate; \
import office_runtime.staff.bundles; \
import office_runtime.staff.briefs; \
import office_runtime.ops.repo_health.policy; \
import office_runtime.ops.repo_health.sheets; \
import office_runtime.ops.repo_health.frontier_export; \
import office_runtime.ops.repo_health.runner; \
import office_runtime.ops.repo_health.plugin_loader; \
import office_runtime.ops.repo_health.remote.source; \
import office_runtime.ops.repo_health.run_bundle.model; \
import office_runtime.ops.repo_health.run_bundle.ports; \
import office_runtime.ops.repo_health.adapters.gcp.bigquery; \
import office_runtime.ops.repo_health.adapters.gcp.storage; \
import office_runtime.ops.repo_health.cloud.run_job; \
import office_runtime.ops.repo_health.compiler.generate; \
import office_runtime.ops.repo_health.compiler.ir; \
import office_runtime.ops.repo_health.compiler.classify; \
import office_runtime.ops.repo_health.plugins.base; \
import office_runtime.ops.repo_health.plugins.git_activity_plugin; \
import office_runtime.ops.repo_health.plugins.make_smoke_plugin; \
import office_runtime.ops.repo_health.plugins.remote_activity_plugin; \
import office_runtime.ops.repo_health.plugins.remote_runbook_plugin; \
import office_runtime.ops.repo_health.plugins.repo_artifact_plugin; \
import office_runtime.ops.repo_health.plugins.repo_env_plugin; \
import office_runtime.ops.repo_health.plugins.repo_runbook_plugin; \
from office_runtime.ops.repo_health.plugin_loader import load_plugins_from_folder; \
plugins = load_plugins_from_folder('src/office_runtime/ops/repo_health/plugins'); \
print('plugins:', sorted(plugins)); \
print('imports ok')"

editorial-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_editorial_contracts

dependency-contracts:
	PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --check
	PYTHONPATH=src python3 -m unittest tests.test_dependency_profiles

systemd-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_systemd_install

runtime-contracts: dependency-contracts systemd-contracts

install-profile:
	@test -n "$(PROFILE)" || (echo "PROFILE is required; use office, capture, repo-health, full, or legacy-auto-checker" >&2; exit 2)
	PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py "$(PROFILE)"

docs-check:
	python3 src/office_runtime/scripts/check_docs.py

parent-docs-check:
	python3 src/office_runtime/scripts/check_docs.py --exclude docs/architecture/editorial-projection.md

audit: docs-check runtime-contracts
	python3 -m compileall src
	$(MAKE) imports
	git diff --check

parent-audit: parent-docs-check runtime-contracts
	python3 -m compileall -q -x '/editorial/' src/office_runtime
	PYTHONPATH=src python3 src/office_runtime/scripts/profile_smoke.py full
	git diff --check

daily:
	PYTHONPATH=src python3 -m office_runtime.cli daily

office-compile:
	PYTHONPATH=src python3 -m office_runtime.cli office compile

staff-bundles:
	PYTHONPATH=src python3 -m office_runtime.cli staff bundles --scan-mode existing

staff-briefs:
	PYTHONPATH=src python3 -m office_runtime.cli staff briefs

capture-lifecycle:
	PYTHONPATH=src python3 -m office_runtime.cli capture lifecycle

repo-health-policy:
	PYTHONPATH=src python3 -m office_runtime.cli ops repo-health policy

repo-health-run:
	PYTHONPATH=src python3 -m office_runtime.cli ops repo-health run

evidence-git:
	PYTHONPATH=src python3 -m office_runtime.cli evidence git --roots $(ROOTS) --start $(START) --end $(END) --out $(GIT_OUT)

evidence-files:
	PYTHONPATH=src python3 -m office_runtime.cli evidence files --roots $(ROOTS) --start $(START) --end $(END) --out $(FILES_OUT)

evidence-today: evidence-git evidence-files

logs-tail:
	@tail -n 30 artifacts/logs/daily/*.ledger.log

repo-scans:
	bash src/office_runtime/scripts/repo_contract_scan.sh "$$PWD" >/tmp/office_auto_lab_prereqs.tsv
	bash src/office_runtime/scripts/repo_snapshot_protocol.sh "$$PWD" >/tmp/office_auto_lab_srp.txt
	test -s /tmp/office_auto_lab_prereqs.tsv
	test -s /tmp/office_auto_lab_srp.txt
	@echo "repo scans ok"

compile-blocks:
	mkdir -p out/frontier
	cp fixtures/frontier_sample_v2.csv out/frontier/latest.csv 2>/dev/null || cp fixtures/frontier_sample.csv out/frontier/latest.csv
	PYTHONPATH=src python3 src/office_runtime/scripts/legacy/compile_blocks.py --frontier out/frontier/latest.csv --date "$$(date +%F)"
	test -s out/compiler/$$(date +%F)/prepared_blocks.jsonl
	@echo "compile blocks ok"

office:
	PYTHONPATH=src python3 -m office_runtime.office.main
