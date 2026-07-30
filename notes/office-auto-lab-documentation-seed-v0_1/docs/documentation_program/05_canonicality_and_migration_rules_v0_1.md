# office-auto-lab documentation canonicality and migration rules v0.1

## Document classes

| Class | Meaning | May contain canonical commands? |
|---|---|---:|
| canonical | current reader-facing source of truth | yes |
| supporting | detailed evidence or subsystem background | only by link |
| historical | accurate record of a past plan/state | no |
| generated | derived reference; regeneration owner must be named | only when generator is canonical |

## Directory policy

- `docs/` is the canonical documentation surface.
- `notes/` or ad hoc Markdown, when present, is working memory and not canonical.
- `context/closures/` and evidence packets preserve execution history.
- `docs/retrofit/gcp_project_health/` remains a governed retrofit record until
  canonical architecture, operations, and case-study pages exist.
- Source-adjacent READMEs may own module-local details but must link to the
  documentation router and avoid duplicating global golden paths.

## Migration protocol

1. Inventory the old page and identify every unique fact.
2. Verify those facts against current source and evidence.
3. Create or update the canonical capability-oriented page.
4. Replace copied command blocks in supporting pages with a link.
5. Add a status banner to the old page:
   - historical;
   - superseded by;
   - last valid commit/timeframe.
6. Check inbound links before moving or deleting.
7. Preserve unique decisions/evidence.
8. Delete only after a human accepts that no unique operational knowledge is lost.

## Naming rules

Prefer:

- `repo-health-gcp.md`
- `capture.md`
- `systemd-automation.md`
- `gcp-project-health-retrofit.md`

Avoid canonical names such as:

- `PR-G4-notes.md`
- `new-final-runbook-v2.md`
- `misc.md`

PR identifiers belong in historical execution records, not durable navigation.

## Update obligations

A PR that changes any of the following must identify the canonical page affected:

- CLI commands or flags;
- Make targets;
- environment variables;
- artifact paths or schemas;
- plugin capabilities;
- systemd units;
- GCP resources, IAM, or deployment steps;
- maturity/status claims.

“No documentation impact” must be justified in the PR.
