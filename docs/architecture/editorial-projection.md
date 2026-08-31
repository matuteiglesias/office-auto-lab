# Editorial projection subsystem

Status: W0 contract seed. No live X mutation is authorized by this document.

## Purpose

`office-auto-lab` hosts the bounded execution code that projects Matias's work and ideas onto public X accounts. It does not own the durable editorial constitution, source-product scientific semantics, or upstream media/economic truth.

The first implementation supports two deliberately different projection profiles rather than one generic social-media agent.

## Profile A — dev

Goal: low-cost projection of software, data, research-engineering, and maintenance work.

Primary evidence:
- recent GitHub commits, merged PRs, releases, and explicit issue decisions;
- when recent work is weak, a governed historical-dev-work bench may provide candidates.

The projector translates technical work into one externally legible lesson or artifact. It must not become a commit feed and must retain exact work references behind every candidate.

The dev account handle is deployment configuration, not repository policy; `X_DEV_ACCOUNT_HANDLE` resolves the public handle and a separate credential set resolves mutation authority.

## Profile B — argentina_econ

Public X identity: `matuteiglesias`.

Goal: participate in current Argentina-economics discussion by grounding timely commentary in Matias-owned evidence and Matias-approved ideas.

Required upstreams:
- `media_monitor` for monitored-media item identity, source metadata, governed text/summary evidence, and timestamps;
- `atlas-economico-ar` for economic questions, indicators, series, and publication-ready plots;
- other governed Matias-owned economic artifacts such as IPC, EPH, poverty, and research outputs as they become eligible;
- an approved Matias idea bank, separate from generated copy;
- fresh public-web context when needed to verify current claims or discussions.

### Claim–evidence–idea triangle

A publishable Argentina-econ candidate requires all three:

1. **current claim** — an exact recent statement/discussion with an inspectable source;
2. **owned evidence** — a plot/series/result Matias actually produced or governs, with exact identity;
3. **approved idea** — an interpretation/proposition already authorized for autonomous projection.

The editorial system classifies the relationship between current claim and owned evidence as exactly one of:

- `supports`
- `contextualizes`
- `complicates`
- `contradicts`
- `historicizes`
- `cannot_adjudicate`

`cannot_adjudicate` is a valid retrieval/judgment outcome and must result in skip/hold, not copy pretending to know more than the evidence establishes.

The projector must not optimize for conflict. It should prefer the strongest evidence relationship, whether supportive, contextual, complicating, contradictory, or historical.

## Shared pipeline

```text
weekly governance / constitution
        ↓
profile-specific evidence retrieval
        ↓
candidate generation
        ↓
independent editorial judgment
        ↓
deterministic policy gate
   ┌────┴────┐
 publish   skip/hold
   ↓
exact X post identity + run evidence
   ↓
24h / 72h metrics
   ↓
weekly bounded experiment review
```

The shared pipeline is intentionally small. Profile-specific retrieval and epistemic requirements remain separate.

## Authority boundaries

### `weekly-ops-governance`
Owns slow editorial policy: public identity thesis, prohibited material, allowed experiment dimensions, auto-publication risk ceiling, kill switch, and changes to the approved idea bank's governance rules.

### `office-auto-lab`
Owns scheduled execution, retrieval orchestration, candidate/judge execution, deterministic gates, X adapters, metrics retrieval, run evidence, and bounded weekly experiment evaluation.

### Upstream product repositories
Keep ownership of their own source identities and semantics. Editorial copies/references their exact public evidence; it must not reconstruct or silently reinterpret upstream truth.

### X
Is an external publication adapter, not an authority for editorial state.

## Initial package boundary

```text
src/office_runtime/editorial/
    contracts.py
    evidence/          # W1
    synthesis/         # W1
    judgment/          # W1
    policy_gate.py     # W1
    run_bundle/        # W1
    experiments/       # W2+
    adapters/x/        # W2/W3

config/editorial/
    profiles.json
    constitution.*     # owned upstream / pinned identity, not invented by runtime
```

Do not create a generic multi-channel publishing framework yet. X is the only proven external publication consumer.

## W0 hardening conclusions for the parent runtime

The new public-mutation workload exposes several existing infrastructure gaps. They should be handled explicitly rather than hidden inside Editorial.

### 1. Dependency profiles — upgrade required before routine live mutation

The repository currently has overlapping `requirements.txt`, `requirements-auto-checker.txt`, and `requirements-repo-health.txt` with different pinning. Existing issue #20 already owns this concern. Editorial must not create a fourth ad-hoc dependency file. W1 dry-run code may stay stdlib-only where practical; external OpenAI/X clients should enter through the eventual reproducible runtime profile.

### 2. Python CI — upgrade required

The repository's only GitHub Actions workflow currently builds the docs site. Before autonomous public mutation, a core Python workflow must verify at least:
- imports/compile;
- Editorial contract/gate tests;
- mutation duplicate protection and fail-closed tests;
- supported dependency profile(s) once #20 resolves them.

This belongs with runtime hardening, not inside the X adapter.

### 3. Run bundles — reuse pattern, do not generalize prematurely

Repo Health already has a strong domain-specific run-bundle pattern: canonical JSON, policy identity/hash, referential validation, reconciled counters, and derived status. Editorial should implement `editorial.run_bundle.v1` using the same design principles.

Do **not** extract a universal run-bundle framework in W0. After Editorial proves a second real use, compare the two implementations and promote only genuinely common primitives (canonical JSON/hash helpers, safe run IDs, atomic writes) if maintenance duplication is real.

### 4. Capability descriptors — reuse design principle locally

Repo Health capability descriptors are intentionally repo-health-local. Editorial should expose its own bounded capability identity/inputs/outputs/side effects/failure/evidence. Do not widen the Repo Health plugin loader into a general agent framework.

### 5. Scheduling — GitHub Actions first

Tracked systemd units remain tied to one local checkout path (existing issue #19). That should be fixed for Office hygiene, but it need not block Editorial. The first unattended Editorial scheduler should be GitHub Actions because it provides isolated runs, secrets, logs, artifacts, and a clear mutation environment.

Local systemd may later become a recovery/manual operator path after #19 is resolved.

### 6. Secrets and account separation — hard requirement

Use distinct secret namespaces/credentials per X profile. The runtime must prove the authenticated X account identity before publishing and refuse an account/profile mismatch.

No secret value, token, private source payload, or raw credential-bearing response may enter run bundles or logs.

## Promotion gates

- **W0**: contracts/profile boundaries only; no external mutation.
- **W1**: dry-run retrieval → candidates → judge → deterministic gate → run bundle.
- **W2**: read-only X account identity/recent-post/metrics integration; prove two-account routing without publishing.
- **W3**: one explicitly authorized live post per profile, with exact post ID, duplicate protection, kill switch, and account-identity proof.
- **W4**: routine `publish_if_safe` only after W3 evidence and explicit promotion.

## Stop rules

Stop rather than publish when:
- the selected profile cannot be cryptographically/operationally tied to the expected authenticated X identity;
- the evidence pack is stale, incomplete, private, or not inspectable enough for the claim;
- Argentina-econ lacks a current-claim/owned-evidence/approved-idea triangle;
- scientific status is ambiguous;
- candidate risk exceeds the low-risk auto-publication ceiling;
- the policy identity cannot be pinned;
- duplicate detection is uncertain;
- the kill switch is active.
