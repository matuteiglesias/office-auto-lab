# Local development and validation

**Status:** canonical
**Audience:** local contributors and operators
**Owner:** office-auto-lab maintainers
**Verified against:** M0 CORE/SIDECAR/COMPAT migration

## Scope

Use this page to prepare Python and run non-network validation. It does not
configure Google Sheets, OpenAI, GCP, or other provider credentials.

The supported active Python runtime versions are **3.11 and 3.12**. Clean CI
verifies the supported `full` runtime on both versions and narrower capability or
compatibility profiles on Python 3.12 where their dedicated checks require them.

## Dependency authority

Do not choose among the old root `requirements*.txt` files by intuition.
Dependency authority is explicit:

- `requirements/constraints.txt` — one source of truth for declared/direct
  dependency versions used by supported profiles, compatibility profiles, and
  test tooling;
- `requirements/profiles/office.txt` — CORE Office compile, Staff, and supporting
  runtime dependencies;
- `requirements/profiles/capture.txt` — Capture SIDECAR model-client dependency;
- `requirements/profiles/full.txt` — exact union of the supported Office + Capture
  runtime;
- `requirements/profiles/repo-health.txt` — compatibility-only historical Repo
  Health local/cloud dependency surface;
- `requirements/profiles/legacy-auto-checker.txt` — compatibility-only historical
  checker environment;
- `requirements/test.txt` — constrained CI/developer tooling only, deliberately
  excluded from runtime capability membership.

The root files `requirements.txt`, `requirements-repo-health.txt`, and
`requirements-auto-checker.txt` are compatibility shims only. They no longer own
versions.

The supported `full` profile deliberately does **not** install Repo Health/GCP
compatibility dependencies. Consumers that still need a compatibility surface
must request its explicit profile. See
[component lifecycle and active product boundary](../architecture/component-lifecycle.md).

Validate the contract without installing anything:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --check
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --list
```

## Setup

For normal supported-runtime development, install `full`:

```bash
python3 -m venv .venv
. .venv/bin/activate
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py full
```

For bounded work, install only the owning supported profile instead:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py office
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py capture
```

For an explicitly scoped compatibility repair or consumer migration, install the
compatibility profile directly rather than adding it back to `full`:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py repo-health
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py legacy-auto-checker
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
make smoke
```

`make runtime-contracts` validates dependency profiles and portable systemd
rendering. `make parent-audit` validates the non-Editorial supported parent
runtime: non-Editorial canonical docs, byte-compilation excluding Editorial,
full-profile imports, dependency/scheduler contracts, and diff hygiene.

`make smoke` is the CORE acceptance surface. It must not invoke compatibility
Repo Health machinery or the legacy prepared-block compiler. Compatibility
components retain dedicated checks until their consumers are migrated.

`make audit` remains the whole-repository gate. It also validates Editorial and
therefore may expose debt owned by that slice; the parent hardening round does not
weaken or silently repair Editorial contracts to make the parent gate pass.

The CLI remains the canonical execution surface. Sibling capabilities remain
explicit (`office`, `staff`, `capture`, `evidence`, and compatibility-only
`ops repo-health`) rather than being treated as one undifferentiated runtime.

## Optional bounded checks

These commands write only caller-selected/local artifacts unless their provider
credentials are configured:

```bash
PYTHONPATH=src python3 -m office_runtime.cli capture lifecycle \
  --inbox-root inbox --out /tmp/office-capture

PYTHONPATH=src python3 -m office_runtime.cli evidence files \
  --roots docs --start 2026-08-31 --end 2026-08-31 \
  --out /tmp/office-evidence/files.jsonl --max-depth 1
```

Compatibility validation, when specifically needed, remains explicit:

```bash
PYTHONPATH=src python3 -m office_runtime.ops.repo_health.cloud.run_job \
  --profile local --policy fixtures/gcp_policy_snapshot.json --validate-only
```

Do not interpret a successful compatibility validation as promotion back into the
supported Office product surface.

## Known semantic boundary

Capture lifecycle/transcription are part of the stable supported parent-runtime
acceptance. The capture-processing ontology failure tracked in issue #21 remains
separate and must not be hidden by infrastructure hardening. Do not interpret
green dependency or scheduler CI as scientific/ontology approval of that
processing path.

## Stop rules

Stop before networked commands if credentials or target identifiers are unclear.
Use explicit `--dry-run` where a capability exposes it. Do not interpret imports,
dependency resolution, or systemd syntax verification as behavioral validation of
an external provider. See [failure recovery](../operations/failure-recovery.md)
for known failures.
