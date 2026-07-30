# Office Auto Lab documentation frontend

This package presents canonical Markdown from repository-root `docs/` without
committing a second authored copy. `npm run sync` copies the curated public set
and the VitePress scaffold into `.generated/site`; checks and VitePress operate
only on that ephemeral tree, and production output goes to `dist/`.

## Local commands

```bash
npm ci
npm run dev       # sync, then local VitePress server
npm run sync      # regenerate the public tree and public-routes.json
npm run check     # policy, routes, navigation, and secret-pattern checks
npm run build     # check plus strict static production build
npm run preview   # serve dist locally
```

`scripts/sync-content.mjs` is the central allow/exclude policy. It admits the
canonical front door, getting-started, architecture, component, operations,
reference, case-study, and selected historical/maintenance pages. It rejects
documentation-program execution records, context, retrofit prompts, notes,
artifacts, environment/state files, and frontmatter explicitly marked internal,
private, draft, or `search: false`. The generated manifest is reviewable at
`.generated/site/public-routes.json` after sync.

Mermaid is rendered with pinned `vitepress-plugin-mermaid`, a small, maintained
VitePress integration that transforms Mermaid fences without introducing an
application framework. `npm run build` exercises its SSR/static rendering path.

## Separate Vercel project handoff

Deployment status: **DEPLOYMENT_READY / BLOCKED_EXTERNAL**. No authenticated
Vercel project or public URL is claimed by this change.

| Setting | Exact value |
|---|---|
| Repository | `matuteiglesias/office-auto-lab` |
| Root Directory | `docs-site` |
| Include source files outside Root Directory | **Enabled** (required for `../docs`) |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Production Branch | `main` |

The install command in `vercel.json` is `npm ci`; clean URLs, immutable hashed
asset caching, and static security headers are configured. There are no
functions. Set `DOCS_SITE_URL` to the real origin (without a trailing slash) to
enable sitemap/canonical-origin generation. A possible future custom domain is
`office-auto-lab-docs.<owner-domain>`; none is assumed.

Smallest human action: import the repository in Vercel, use the table above,
enable the monorepo source-files toggle, and deploy. With authenticated CLI
access, from the repository root:

```bash
cd docs-site
npx vercel link                 # select/create only the docs project
npx vercel deploy               # preview
npx vercel inspect <preview-url>
npx vercel deploy --prod        # only after preview review
```

Record the real preview URL and route checks before changing status to
`PUBLICLY_AVAILABLE`.
