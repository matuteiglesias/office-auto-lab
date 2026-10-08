# Media Evidence Composition Sidecar

## Purpose

Turn an already-governed Media Monitor summary store into one KB Artifacts named-corpus topic/date selection without moving source semantics into Office.

Ownership remains:

- Media Monitor owns `media_summary.v1` and `producer-local:media-monitor.evidence-jsonl@1`.
- KB Artifacts owns generic selection and `artifact:kb.selected-evidence@1`.
- Matías Context MCP owns checksum-bound evidence transport.
- Office owns only bounded orchestration between those existing interfaces.

## Safe plan

Without `--apply`, the command validates identities/arguments and prints the exact producer/selector plan without creating evidence or a selection:

    PYTHONPATH=src python3 src/office_runtime/scripts/compose_media_evidence.py \
      --selection-id media-inflation-20261007 \
      --from 2026-10-05 --to 2026-10-07 \
      --topic 'inflaci[oó]n' \
      --media-monitor-root /path/to/media_monitor \
      --media-store-root /path/to/governed/media/store \
      --kb-artifacts-root /path/to/kb-artifacts

## Apply

Add `--apply` only when generating the derived KB selection is intended.

The sidecar then:

1. runs Media Monitor's own evidence exporter;
2. builds a temporary `media-monitor` named-corpus profile around that export;
3. invokes KB Artifacts' own `select` command with the requested inclusive date window and topic regex;
4. requires a non-empty selection and a manifest checksum for `selected.jsonl`;
5. returns `ops.media-evidence-composition-receipt@1` with the exact MCP handoff.

Example handoff:

    mctx evidence media-inflation-20261007

## Safety / stop conditions

- Existing selection IDs are never overwritten.
- Repository roots must expose the expected governed SYSTEM identities.
- The sidecar does not call Gemini, YouTube, or MCP itself.
- It does not alter canonical Media items/summaries.
- It does not implement selection semantics; it invokes KB Artifacts.
- It does not synthesize claims; that remains a reasoning-client operation over `mctx evidence`.
- Failure in either producer export or selector stops without reporting success.

Generated work files under Office are local orchestration evidence. The durable selected-evidence run remains a KB Artifacts output.
