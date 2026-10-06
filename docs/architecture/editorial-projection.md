# Editorial projection subsystem

**Status:** W0 authority/contract seed; dev-profile W1 staging is specified in `docs/spec/editorial-v1/`  
**Audience:** editorial projection maintainers and agents  
**Owner:** office-auto-lab maintainers  
**Verified against:** W0 contract seed plus Editorial Dev Staging v1 specification; no live X mutation is authorized by this document

> **Canonical dev-staging spec:** `docs/spec/editorial-v1/README.md`.  
> This document remains authoritative for the shared profile/authority boundary and future live-publication promotion gates. The v1 bundle is authoritative for the `dev` profile's daily evidence-to-candidate staging behavior.

## Purpose

`office-auto-lab` hosts the bounded execution code that projects Matias's work and ideas onto public X accounts. It does not own the durable editorial constitution, source-product scientific semantics, or upstream media/economic truth.

The first implementation supports two deliberately different projection profiles rather than one generic social-media agent.

## Profile A — dev

Goal: low-cost projection of software, data, research-engineering, and maintenance work.

Primary evidence:
- recent GitHub commits, merged PRs, releases, and explicit issue decisions;
- broader governed activity evidence as admitted by the dev-staging contracts;
- when recent work is weak, a governed historical-dev-work bench may provide candidates.

The projector translates technical work into externally legible lessons, artifacts, questions, failures, tradeoffs, measurements, field notes, or syntheses. It must not become a commit feed and must retain exact work references behind every candidate.

The dev profile is now deliberately split into two semantic capabilities:

1. **staging** — continuously maintain an evidence-backed candidate inventory and human-editable queue;
2. **publication** — later select/schedule/publish candidates under explicit publication policy.

W1 implements staging only. A staged candidate is not approval and creates no external side effect.

The dev account handle is deployment configuration, not repository policy; `X_DEV_ACCOUNT_HANDLE` resolves the public handle and a separate credential set resolves future mutation authority.

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

The durable semantic pipeline is:

```text
slow editorial governance / constitution
        ↓
profile-specific evidence retrieval
        ↓
structured evidence + story/angle generation
        ↓
independent editorial judgment
        ↓
deterministic staging gates
        ↓
candidate inventory + immutable run evidence
        ↓
human/policy queue
        ↓
future publication policy / publisher
        ↓
exact X post identity + mutation evidence
        ↓
24h / 72h metrics
        ↓
bounded experiment review
```

For `dev`, the W1 boundary stops at the queue. For future live mutation, publication remains separately gated by the promotion sequence below.

The shared pipeline is intentionally small. Profile-specific retrieval and epistemic requirements remain separate.

## Authority boundaries

### `weekly-ops-governance`

Owns slow editorial policy: public identity thesis, prohibited material, allowed experiment dimensions, auto-publication risk ceiling, kill switch, and changes to the approved idea bank's governance rules.

Time-bounded launch-week issues are historical once their stated window expires; unattended runtime must pin a current policy/constitution rather than assume an old issue remains current.

### `office-auto-lab`

Owns scheduled execution, retrieval orchestration, candidate/judge execution, deterministic gates, run evidence, queue projection, future X adapters, metrics retrieval, and bounded experiment evaluation after each capability is explicitly promoted.

### `projects`

Owns GitHub-estate identity, producer/surface governance, and advisory estate context. It must not become an Editorial runtime dependency or execute participating repositories.

### Upstream product repositories

Keep ownership of their own source identities and semantics. Editorial copies/references their exact evidence; it must not reconstruct or silently reinterpret upstream truth.

### Google Sheet staging surface

Owns high-frequency human editorial state only after it is materialized and governed. Machine-generated provenance remains in Office run evidence. The staging producer must preserve human-owned queue fields.

### X

Is an external publication adapter, not an authority for editorial state.

## Initial package boundary

```text
src/office_runtime/editorial/
    contracts.py
    evidence/
    synthesis/
    judgment/
    policy_gate.py
    run_bundle/
    staging/
    adapters/
        sheets/
        x/              # future publication wave

config/editorial/
    profiles.json
    constitution.*     # owned upstream / pinned identity, not invented by runtime

docs/spec/editorial-v1/
    README.md
    PRODUCT.md
    ARCHITECTURE.md
    CONTRACTS.md
    ACCEPTANCE.md
    DEVELOPMENT_DAG.md
    OPERATIONS.md
```

Do not create a generic multi-channel publishing framework yet. X is the first proven external publication consumer, while LinkedIn/long-form remain future downstream consumers of stable candidate artifacts.

## Framework boundary

Agent/orchestration frameworks are implementation details.

The `dev` W1 implementation may use Google ADK for the structured angle/editor workflow, while another domain subsystem such as Media Monitor may use another framework. Downstream components depend on Office Editorial contracts, not ADK session objects or provider-specific types.

## W0 hardening conclusions for the parent runtime

### 1. Dependency authority

Editorial must use the repository's canonical dependency constraints/profile machinery. Do not add an ad-hoc requirements file.

### 2. Python CI

Before autonomous public mutation, core CI must verify:
- imports/compile;
- Editorial contract/gate tests;
- mutation duplicate protection and fail-closed tests;
- supported dependency profiles.

W1 staging should already test contract validation, idempotent projection, and human-state preservation.

### 3. Run bundles

Editorial implements `editorial.run_bundle.v1` using canonical JSON, stable IDs, pinned policy identity, referential validation, reconciled counters/status, and atomic evidence writes.

Do not extract a universal run-bundle framework merely because another subsystem has similar mechanics.

### 4. Capability descriptors

Editorial exposes its own bounded capability identity/inputs/outputs/side effects/failure/evidence. Do not widen unrelated plugin loaders into a generic agent framework.

### 5. Scheduling

GitHub Actions remains the first unattended Editorial scheduler because it provides isolated runs, secrets, logs, artifacts, and a clear mutation environment. Scheduler choice must not define producer identity.

### 6. Secrets and account separation

Use distinct secret namespaces/credentials per future X profile. The runtime must prove authenticated X account identity before publishing and refuse an account/profile mismatch.

No secret value, token, private source payload, or raw credential-bearing response may enter run bundles or logs.

## Promotion gates

- **W0**: contracts/profile boundaries only; no external mutation.
- **W1**: unattended evidence retrieval → story/angles → independent editorial judgment → daily candidate inventory → immutable run bundle → human-editable staging queue. **No X mutation.**
- **W2**: read-only X account identity/recent-post/metrics integration and publisher-policy contract; prove account routing without publishing.
- **W3**: one explicitly authorized live post per profile, with exact post ID, duplicate protection, kill switch, and account-identity proof.
- **W4**: routine publication only after W3 evidence and explicit promotion.

## Stop rules

Stop rather than stage/publish when the relevant boundary cannot be proven.

For staging:
- policy identity cannot be pinned;
- evidence is stale, incomplete, private, or not inspectable enough for the claim;
- source status needed by the copy is unknown;
- generated evidence refs do not resolve;
- human/machine Sheet ownership is ambiguous;
- duplicate/idempotency state is uncertain;
- privacy/sensitive-topic gate fails.

For future publication, additionally stop when:
- the selected profile cannot be cryptographically/operationally tied to the expected authenticated X identity;
- Argentina-econ lacks its current-claim/owned-evidence/approved-idea triangle;
- scientific status is ambiguous;
- candidate risk exceeds the publication ceiling;
- cadence/duplicate policy is uncertain;
- the kill switch is active.
