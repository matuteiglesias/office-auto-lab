# Local development and validation

**Status:** canonical
**Audience:** local contributors and operators
**Owner:** office-auto-lab maintainers
**Verified against:** pre-editorial parent-runtime hardening round

## Scope

Use this page to prepare Python and run non-network validation. It does not
configure Google Sheets, OpenAI, GCP, or other provider credentials.

The supported active Python runtime versions are **3.11 and 3.12**. Clean CI
verifies the complete active runtime on both versions and each narrower
capability profile on Python 3.12.

## Dependency authority

Do not choose among the old root `requirements*.txt` files by intuition.
Dependency authority is now explicit:

- `requirements/constraints.txt` — one source of truth for declared/direct
  dependency versions used by supported profiles and test tooling;
- `requirements/profiles/office.txt` — Office compile, staff, and evidence
  dependencies;
- `requirements/profiles/capture.txt` — Capture's model-client dependency;
- `requirements/profiles/repo-health.txt` — Repo Health local/cloud dependency
  surface;
- `requirements/profiles/full.txt` — exact union of the active profiles;
- `requirements/profiles/legacy-auto-checker.txt` — compatibility-only historical
  checker environment; it is not part of the active full runtime;
- `requirements/test.txt` — constrained CI/developer tooling only, deliberately
  excluded from runtime capability membership.

The root files `requirements.txt`, `requirements-repo-health.txt`, and
`requirements-auto-checker.txt` are compatibility shims only. They no longer own
versions.

Validate the contract without installing anything:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --check
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --list
```

## Setup

For normal development, install the active full profile:

```bash
python3 -m venv .venv
. .venv/bin/activate
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py full
```

For bounded work, install only the owning capability profile instead:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py office
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py capture
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py repo-health
```

When running suites that import test-only packages:

```bash
python3 -m pip install -c requirements/constraints.txt -r requirements/test.txt
```

`make install-profile PROFILE=<name>` is an equivalent contributor convenience.
Unsupported profile names fail with an explicit list rather than composing an
untested environment.

The constraints file pins the repository's declared/direct dependency surface.
Clean CI proves that those constraints resolve consistently enough for supported
profiles on Python 3.11/3.12, but this is **not yet a committed transitive lock**.
Issue #20 retains that stronger reproducibility question; do not describe it as
closed until the resolver graph is intentionally frozen or the requirement is
explicitly revised.

## Parent-runtime preflight

After installing `full`:

```bash
PYTHONPATH=src python3 -m office_runtime.cli --help
make runtime-contracts
make parent-audit
```

`make runtime-contracts` validates dependency profiles and portable systemd
rendering. `make parent-audit` validates the non-Editorial parent runtime:
non-Editorial canonical docs, byte-compilation excluding Editorial, full-profile
imports, dependency/scheduler contracts, and diff hygiene.

`make audit` remains the whole-repository gate. It also validates Editorial and
therefore may expose debt owned by that slice; the pre-Editorial hardening round
does not weaken or silently repair Editorial contracts to make the parent gate
pass.

The CLI remains the canonical execution surface. It intentionally keeps sibling
capabilities separate (`office`, `staff`, `ops`, `capture`, `evidence`) rather
than introducing another workflow framework.

## Optional bounded checks

These commands write only caller-selected/local artifacts unless their provider
credentials are configured:

```bash
PYTHONPATH=src python3 -m office_runtime.cli capture lifecycle \
  --inbox-root inbox --out /tmp/office-capture

PYTHONPATH=src python3 -m office_runtime.cli evidence files \
  --roots docs --start 2026-08-31 --end 2026-08-31 \
  --out /tmp/office-evidence/files.jsonl --max-depth 1

PYTHONPATH=src python3 -m office_runtime.ops.repo_health.cloud.run_job \
  --profile local --policy fixtures/gcp_policy_snapshot.json --validate-only
```

`make smoke` is now a valid tracked-path smoke target, but it does more work than
the first-contact checks above and may generate local compiler artifacts. Use it
when that wider acceptance is intended.

## Known semantic boundary

Capture lifecycle/transcription are part of the stable parent-runtime acceptance.
The capture-processing ontology failure tracked in issue #21 remains separate and
must not be hidden by infrastructure hardening. Do not interpret green dependency
or scheduler CI as scientific/ontology approval of that processing path.

## Stop rules

Stop before networked commands if credentials or target identifiers are unclear.
Use explicit `--dry-run` where a capability exposes it. Do not interpret imports,
dependency resolution, or systemd syntax verification as behavioral validation of
an external provider. See [failure recovery](../operations/failure-recovery.md)
for known failures.
