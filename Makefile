.PHONY: imports docs-check parent-docs-check audit parent-audit office-v2-generate office-v2-shadow frontier-view-v1 frontier-view-v1-contracts runtime-health-v2 capture-lifecycle evidence-git evidence-files estate-movement smoke control-contracts identity-contracts work-contracts staff-v2-contracts principal-contracts execution-contracts reentry-v2-contracts generation-v2-contracts run-record-contracts freshness-contracts editorial-contracts dependency-contracts systemd-contracts runtime-contracts install-profile repo-scans evidence-today logs-tail

ROOTS ?= .
START ?= $(shell date +%F)
END ?= $(shell date +%F)
OUT_DIR ?= artifacts/evidence
ESTATE_OUT_DIR ?= artifacts/estate-movement
GIT_OUT ?= $(OUT_DIR)/git_trace/$(START)_$(END).jsonl
FILES_OUT ?= $(OUT_DIR)/fs_trace/$(START)_$(END).jsonl

# Supported product acceptance: Office v2 CORE plus declared sidecars only.
smoke: imports control-contracts identity-contracts work-contracts staff-v2-contracts principal-contracts execution-contracts reentry-v2-contracts generation-v2-contracts frontier-view-v1-contracts run-record-contracts freshness-contracts editorial-contracts runtime-contracts repo-scans

imports:
	PYTHONPATH=src python3 -c "import office_runtime; \
import office_runtime.cli; \
import office_runtime.capture; \
import office_runtime.capture.lifecycle; \
import office_runtime.editorial; \
import office_runtime.editorial.contracts; \
import office_runtime.office.config; \
import office_runtime.office.control_snapshot; \
import office_runtime.office.identity; \
import office_runtime.office.work_items; \
import office_runtime.office.principal; \
import office_runtime.office.execution; \
import office_runtime.office.reentry_v2; \
import office_runtime.office.generation_v2; \
import office_runtime.office.frontier_view; \
import office_runtime.office.invariants; \
import office_runtime.office.run_records; \
import office_runtime.office.io; \
import office_runtime.staff.preparation_v2; \
import office_runtime.staff.freshness; \
print('imports ok')"

control-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_control_snapshot_v2

identity-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_identity_resolution_v2

work-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_work_item_compiler_v1

staff-v2-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_staff_preparation_v2

principal-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_principal_compiler_v2

execution-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_execution_compiler_v2

reentry-v2-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_reentry_v2

generation-v2-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_generation_v2 tests.test_generation_run_records tests.test_battletest_projection

frontier-view-v1-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_frontier_view_v1

run-record-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_run_record_health tests.test_generation_invariants

freshness-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_staff_packet_freshness

editorial-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_editorial_contracts

dependency-contracts:
	PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --check
	PYTHONPATH=src python3 -m unittest tests.test_dependency_profiles

systemd-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_systemd_install

runtime-contracts: dependency-contracts systemd-contracts

install-profile:
	@test -n "$(PROFILE)" || (echo "PROFILE is required; choose office, capture, or full" >&2; exit 2)
	PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py "$(PROFILE)"

docs-check:
	python3 src/office_runtime/scripts/check_docs.py

parent-docs-check:
	python3 src/office_runtime/scripts/check_docs.py --exclude docs/architecture/editorial-projection.md

audit: docs-check runtime-contracts
	python3 -m compileall src
	$(MAKE) imports
	git diff --check

parent-audit: parent-docs-check runtime-contracts control-contracts identity-contracts work-contracts staff-v2-contracts principal-contracts execution-contracts reentry-v2-contracts generation-v2-contracts run-record-contracts freshness-contracts
	python3 -m compileall -q -x '/editorial/' src/office_runtime
	PYTHONPATH=src python3 src/office_runtime/scripts/profile_smoke.py full
	git diff --check

# Canonical Office runtime entrypoints.
office-v2-generate:
	PYTHONPATH=src python3 src/office_runtime/scripts/run_generation_v2.py --trigger manual

office-v2-shadow:
	PYTHONPATH=src python3 src/office_runtime/scripts/run_generation_v2.py --shadow --trigger shadow-check

# Read-only Event & Institutional Frontier projection. Optional export path is
# controlled by FRONTIER_VIEW_EXPORT_PATH; this never mutates Control Tower.
frontier-view-v1:
	PYTHONPATH=src python3 src/office_runtime/scripts/compile_frontier_view_v1.py

# Run Record Owner projection. This never mutates Carry/priority state.
runtime-health-v2:
	PYTHONPATH=src python3 src/office_runtime/scripts/compile_runtime_health_v2.py

capture-lifecycle:
	PYTHONPATH=src python3 -m office_runtime.cli capture lifecycle

evidence-git:
	PYTHONPATH=src python3 -m office_runtime.cli evidence git --roots $(ROOTS) --start $(START) --end $(END) --out $(GIT_OUT)

evidence-files:
	PYTHONPATH=src python3 -m office_runtime.cli evidence files --roots $(ROOTS) --start $(START) --end $(END) --out $(FILES_OUT)

evidence-today: evidence-git evidence-files

# Read-only estate delta producer. Review output never auto-mutates governance.
estate-movement:
	@test -n "$(ROOTS)" || (echo "ROOTS is required" >&2; exit 2)
	@test -n "$(START)" || (echo "START is required" >&2; exit 2)
	@test -n "$(END)" || (echo "END is required" >&2; exit 2)
	@test -n "$(DIGEST_ID)" || (echo "DIGEST_ID is required" >&2; exit 2)
	PYTHONPATH=src python3 -m office_runtime.cli estate movement --digest-id "$(DIGEST_ID)" --roots $(ROOTS) --start "$(START)" --end "$(END)" --out-root "$(ESTATE_OUT_DIR)" $(if $(PREVIOUS_MANIFEST),--previous-manifest "$(PREVIOUS_MANIFEST)") $(if $(CONTROL_PLANE),--control-plane "$(CONTROL_PLANE)")

logs-tail:
	@tail -n 30 artifacts/logs/daily/*.ledger.log

repo-scans:
	bash src/office_runtime/scripts/repo_contract_scan.sh "$$PWD" >/tmp/office_auto_lab_prereqs.tsv
	bash src/office_runtime/scripts/repo_snapshot_protocol.sh "$$PWD" >/tmp/office_auto_lab_srp.txt
	test -s /tmp/office_auto_lab_prereqs.tsv
	test -s /tmp/office_auto_lab_srp.txt
	@echo "repo scans ok"
