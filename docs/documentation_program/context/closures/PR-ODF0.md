# PR-ODF0 — public documentation frontend closure

**Track:** presentation and availability (separate from the accepted OD0–OD6
canonical documentation program)
**State:** `DEPLOYMENT_READY / BLOCKED_EXTERNAL`

## Before and after

Before this change, canonical documentation was browsable only as repository
Markdown. The change adds an isolated VitePress presentation package that
curates canonical pages into a generated, ignored source tree and emits a static
site. Canonical files remain under `docs/`; product behavior and documentation
program carry state are unchanged.

## Evidence and boundary

- Lockfile installation, public-content checks, and the strict production build
  passed locally.
- The generated manifest contains the explicit public set and excludes program
  governance, context, raw retrofit material, notes, state, and private/draft
  markers.
- Desktop and mobile screenshots are local ignored review evidence when browser
  tooling is available.
- Vercel credentials/project access were not available. There is no preview URL
  and no claim of public availability. `docs-site/README.md` contains the exact
  separate-project handoff and the smallest remaining action.

## Review surface

Review `docs-site/scripts/sync-content.mjs` for the boundary, generated
`public-routes.json` after `npm run sync`, the curated navigation in the
VitePress config, custom theme and homepage, `vercel.json`, and the dedicated
GitHub Actions build. Human review owns deployment and acceptance; do not
self-merge.
