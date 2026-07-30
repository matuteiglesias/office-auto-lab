# office-auto-lab documentation seed bundle

This bundle is a repository-root overlay. Copy its contents into the root of
`matuteiglesias/office-auto-lab`.

It intentionally does **not** rewrite existing documentation. It adds:

- a root `AGENTS.md` directing agents to the documentation program;
- a documentation charter and current-state inventory;
- the target documentation stack;
- a seven-PR production sequence;
- quality, canonicality, and migration rules;
- Codex-ready prompts and carry state;
- reusable page, runbook, ADR, and closure templates.

Recommended seed commit:

```bash
git add AGENTS.md docs/documentation_program
git commit -m "docs: seed governed documentation program"
```

After merge, instruct Codex:

> Read `docs/documentation_program/CODEX_START_HERE.md` and execute only the PR
> named by `next_pr`.
