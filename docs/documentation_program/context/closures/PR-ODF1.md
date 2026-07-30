# PR-ODF1 closure — VitePress navigation and Mermaid runtime

## Result

The client navigation failure was a CSP/hydration failure, not a Mermaid parser
failure. The VitePress config supplied a function-valued `editLink.pattern`.
VitePress serializes functions into page data and restores them with
`new Function`; Vercel's intentionally restrictive `script-src` does not allow
`unsafe-eval`, so production hydration stopped before the router attached.
Static HTML still made links look interactive, which explains why curl route
checks did not expose the defect.

The edit-link pattern is now data-only, and RouteCard uses VitePress's router-aware
`VPLink`. Production preview sends the same CSP as Vercel so this regression is
covered without weakening policy. Chromium smoke tests cover desktop and 390 px
mobile navigation, history, clean deep links/reload, custom 404, runtime errors,
CSP violations, and every public Mermaid block in both color schemes.

## Evidence

Local production evidence on 2026-07-30:

- `npm ci`: completed.
- `npm run check`: 33 unique public routes passed policy and route checks.
- `npm run build`: VitePress 1.6.4 production build completed.
- `npm run preview -- --host 127.0.0.1`: served the built site with the deployment CSP.
- `npm run test:browser`: Playwright Chromium smoke passed.

Mermaid rendered before and after client navigation without parser output or
uncaught errors. Navigation also passed on pages with no Mermaid, establishing
that Mermaid initialization was not the trigger.

## Deployment status

**BLOCKED_EXTERNAL.** The GitHub deployment API reports the existing Vercel URL
`https://office-auto-nbceow5w2-matias-projects-5c20d82c.vercel.app`, but it
redirects this unauthenticated environment to Vercel login (deployment
protection). No Vercel token/project credentials are present, so a new preview
cannot honestly be deployed or browser-verified here.

After merge or with project credentials, redeploy from `docs-site` using
`npx vercel deploy`, then run:

```bash
DOCS_PREVIEW_URL=https://<preview-host> npm run test:browser
```

Remove deployment protection for public production access, or provide the
Playwright environment with Vercel protection-bypass credentials.
