.PHONY: imports docs-check parent-docs-check audit parent-audit daily office-compile office-reentry staff-bundles staff-briefs capture-lifecycle evidence-git evidence-files estate-movement smoke control-contracts identity-contracts work-contracts staff-v2-contracts principal-contracts execution-contracts reentry-v2-contracts editorial-contracts dependency-contracts systemd-contracts runtime-contracts install-profile repo-scans evidence-today logs-tail compat-compile-blocks compat-repo-health-policy compat-repo-health-run

ROOTS ?= .
START ?= $(shell date +%F)
END ?= $(shell date +%F)
OUT_DIR ?= artifacts/evidence
ESTATE_OUT_DIR ?= artifacts/estate-movement
GIT_OUT ?= $(OUT_DIR)/git_trace/$(START)_$(END).jsonl
FILES_OUT ?= $(OUT_DIR)/fs_trace/$(START)_$(END).jsonl

# Supported CORE acceptance only. SIDECAR/COMPAT components retain dedicated
# contract/test slices and must not become implicit dependencies of this smoke.
smoke: imports control-contracts identity-contracts work-contracts staff-v2-contracts principal-contracts execution-contracts reentry-v2-contracts editorial-contracts runtime-contracts repo-scans

# Active Office product surface only. Repo Health remains compatibility code and
# is validated separately by its dedicated CI profile/tests.
imports:
	PYTHONPATH=src python3 -c "import office_runtime; \
import office_runtime.cli; \
import office_runtime.capture; \
import office_runtime.capture.lifecycle; \
import office_runtime.editorial; \
import office_runtime.editorial.contracts; \
import office_runtime.office.compile; \
import office_runtime.office.config; \
import office_runtime.office.control_snapshot; \
import office_runtime.office.identity; \
import office_runtime.office.work_items; \
import office_runtime.office.principal; \
import office_runtime.office.execution; \
import office_runtime.office.reentry_v2; \
import office_runtime.office.io; \
import office_runtime.office.render; \
import office_runtime.office.validate; \
import office_runtime.office.closure_reentry; \
import office_runtime.staff.bundles; \
import office_runtime.staff.briefs; \
import office_runtime.staff.preparation_v2; \
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

editorial-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_editorial_contracts

dependency-contracts:
	PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --check
	PYTHONPATH=src python3 -m unittest tests.test_dependency_profiles

systemd-contracts:
	PYTHONPATH=src python3 -m unittest tests.test_systemd_install

runtime-contracts: dependency-contracts systemd-contracts

install-profile:
	@test -n "$(PROFILE)" || (echo "PROFILE is required; active profiles include office, capture, and full; repo-health and legacy-auto-checker are compatibility profiles" >&2; exit 2)
	PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py "$(PROFILE)"

docs-check:
	python3 src/office_runtime/scripts/check_docs.py

parent-docs-check:
	python3 src/office_runtime/scripts/check_docs.py --exclude docs/architecture/editorial-projection.md

audit: docs-check runtime-contracts
	python3 -m compileall src
	$(MAKE) imports
	git diff --check

parent-audit: parent-docs-check runtime-contracts control-contracts identity-contracts work-contracts staff-v2-contracts principal-contracts execution-contracts reentry-v2-contracts
	python3 -m compileall -q -x '/editorial/' src/office_runtime
	PYTHONPATH=src python3 src/office_runtime/scripts/profile_smoke.py full
	git diff --check

daily:
	PYTHONPATH=src python3 -m office_runtime.cli daily

office-compile:
	PYTHONPATH=src python3 -m office_runtime.cli office compile

# Read-only closure intake. Inputs are explicit; this target never writes
# Office sheets or applies Ops recommendations.
office-reentry:
	@test -n "$(CLOSURES)" || (echo "CLOSURES is required" >&2; exit 2)
	@test -n "$(FRONT_REGISTRY)" || (echo "FRONT_REGISTRY is required" >&2; exit 2)
	@test -n "$(REENTRY_OUT)" || (echo "REENTRY_OUT is required" >&2; exit 2)
	PYTHONPATH=src python3 -m office_runtime.cli office reentry compile --closures "$(CLOSURES)" --front-registry "$(FRONT_REGISTRY)" --out "$(REENTRY_OUT)"

staff-bundles:
	PYTHONPATH=src python3 -m office_runtime.cli staff bundles --scan-mode existing

staff-briefs:
	PYTHONPATH=src python3 -m office_runtime.cli staff briefs

capture-lifecycle:
	PYTHONPATH=src python3 -m office_runtime.cli capture lifecycle

# Compatibility-only entrypoints retained during consumer migration.
compat-repo-health-policy:
	PYTHONPATH=src python3 -m office_runtime.cli ops repo-health policy

compat-repo-health-run:
	PYTHONPATH=src python3 -m office_runtime.cli ops repo-health run

evidence-git:
	PYTHONPATH=src python3 -m office_runtime.cli evidence git --roots $(ROOTS) --start $(START) --end $(END) --out $(GIT_OUT)

evidence-files:
	PYTHONPATH=src python3 -m office_runtime.cli evidence files --roots $(ROOTS) --start $(START) --end $(END) --out $(FILES_OUT)

evidence-today: evidence-git evidence-files

# Read-only delta producer. ROOTS, START, END, and DIGEST_ID are explicit to
# prevent accidental broad estate scans; PREVIOUS_MANIFEST is optional.
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

# Compatibility-only legacy prepared-block compiler. This remains callable for
# migration consumers but is intentionally excluded from active smoke/acceptance.
compat-compile-blocks:
	mkdir -p out/frontier
	cp fixtures/frontier_sample_v2.csv out/frontier/latest.csv 2>/dev/null || cp fixtures/frontier_sample.csv out/frontier/latest.csv
	PYTHONPATH=src python3 src/office_runtime/scripts/legacy/compile_blocks.py --frontier out/frontier/latest.csv --date "$$(date +%F)"
	test -s out/compiler/$$(date +%F)/prepared_blocks.jsonl
	@echo "compat compile blocks ok"
