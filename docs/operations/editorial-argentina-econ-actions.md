# Editorial Argentina Econ — GitHub Actions-only authentication

**Status:** alternative, unpromoted
**Audience:** editorial operators and release engineers
**Owner:** office-auto-lab Editorial publisher
**Verified against:** `argentina_econ` OAuth1 profile, PR #74

Do not enable recurring mutation until an
OAuth1 identity proof and two independent cloud dry-runs succeed.

This is a bounded alternative to the already-merged OAuth2+GCS implementation.
The **publishing runtime remains GitHub Actions** in both cases. This option
eliminates GCS entirely by using static OAuth1 user-context credentials in
one GitHub Actions encrypted secret. It never copies ModernAIDev credentials.

## Bound account

- `argentina_econ`, account key `x_argentina_econ`
- `@matuteiglesias`, exact numeric user ID **57242581**
- App `argentina-econ-editorial`, auth **oauth1**
- Sheet `1LAVlYY3T7POA3IUydn3zy2MQBrxc-3c1w-iUq7oFtgo`
- One approved low-risk due post per run; **one per 24 hours**
- Workflow schedule `7,37 * * * *` UTC, best effort; skips >75 minutes stale slots.
- No Cloud Run, Cloud Scheduler, GCS, service-account IAM changes, or OAuth2
  refresh-state synchronization.

## Why OAuth1

X supports OAuth1 user-context auth for `POST /2/tweets`. The four credentials
(API key, API secret, user access token, user access-token secret) are stable
until revoked, rotated or made invalid by permission changes. Each ephemeral
GitHub runner reconstructs `~/.xurl/auth.yml` using a repository Secret.
The same Github Actions secret need not be modified after every execution.

References:
- https://github.com/xdevplatform/docs/blob/main/x-api/posts/manage-tweets/quickstart.mdx
- https://github.com/xdevplatform/xurl/blob/main/README.md
- https://pkg.go.dev/github.com/xdevplatform/xurl/store

## 1. Operator-only setup on local machine

In the X Developer Console open **the existing economics app**, not
ModernAIDev. Configure user authentication for **Read and Write**. In
**Keys and Tokens** obtain that app's OAuth1 API Key/Secret and the
`@matuteiglesias` user Access Token/Secret. If the UI does not support
user-context OAuth1 for this app, DO NOT fabricate tokens: keep the existing
OAuth2+GCS design.

Register the economics OAuth1 credentials with local xurl, without pasting
secrets into Codex prompts, chat, repo, logs or terminal history. `xurl auth
oauth1 --help` can confirm CLI flags. The expected app-scoped CLI is
`xurl auth oauth1 --app argentina-econ-editorial --consumer-key ... --consumer-secret ... --access-token ... --token-secret ...`.

**Read-only proof** (must display the correct user and numeric ID):

```bash
xurl --app argentina-econ-editorial --auth oauth1 whoami
xurl auth status
```

Do not change `modernai-editorial`, the default app, or the existing
economics OAuth2 identity. Do not post during qualification.

Prepare an isolated temporary `xurl` auth.yml with **only** the
`argentina-econ-editorial` app and one `oauth1_token`; do not submit
the entire local `~/.xurl/auth.yml`. Match the current xurl 1.3.4
schema. `editorial_econ_oauth1_secret.validate` checks:
- `default_app == argentina-econ-editorial`;
- the sole app is `argentina-econ-editorial`;
- `oauth1_token.type == oauth1`;
- all four OAuth1 fields exist;
- no `oauth2_tokens` or `bearer_token`.

With your authenticated `gh` CLI (outside agent prompt), provision the
repository secret from the private temp file, without displaying its contents:

```bash
gh secret set EDITORIAL_ECON_XURL_OAUTH1_YAML --repo matuteiglesias/office-auto-lab < /path/to/econ-only-auth.yml
```

Remove the temporary secret-export file securely as appropriate and make
sure the original local xurl credentials retain tight filesystem permissions.
Credential rotation remains an operator procedure; a rotated user token
must be replaced in this GitHub secret before cloud jobs run.

## 2. GitHub Actions variables

Set under **Settings → Secrets and variables → Actions → Variables**:

```text
EDITORIAL_ARGENTINA_ECON_SHEET_ID=1LAVlYY3T7POA3IUydn3zy2MQBrxc-3c1w-iUq7oFtgo
EDITORIAL_ECON_SCHEDULER_ENABLED=false
EDITORIAL_ECON_PUBLISH_ENABLED=false
EDITORIAL_ECON_RUNTIME_PROMOTED=false
EDITORIAL_ARGENTINA_ECON_PUBLISHER_DISABLED=1
```

The existing `EDITORIAL_GOOGLE_CREDENTIALS_JSON` secret is reused **only
for the Google Sheet**. No new Google Cloud bucket or IAM permission is
needed. `EDITORIAL_ECON_AUTH_GCS_BUCKET` and
`EDITORIAL_ECON_AUTH_GCS_OBJECT` are **not used** by this workflow, even
if they happen to exist.

The economics OAuth1 secret is not available to other X publishing
identities by application logic, but remember that repository collaborators
who can change Actions workflows may be able to misuse repository secrets;
review and protect writes to workflows.

## 3. Promotion

1. With scheduler and publisher variables still disabled, run local tests:
   `PYTHONPATH=src python -m unittest tests.test_editorial_econ_oauth1_secret
   tests.test_editorial_argentina_cycle tests.test_editorial_publisher`.
2. Validate `xurl 1.3.4` syntax, actual OAuth1 YAML shape and the
   read-only account identity. If the client cannot use the serialized
   secret, stop. Do not merge simply because mocks passed.
3. Validate workflow syntax and ensure the GitHub Actions dry run is
   read-only. Merging source doesn't itself authorize a post.
4. Merge only after review; run the workflow on main via
   `workflow_dispatch → mode=dry_run` **twice** in independent ephemeral
   runners. Verify Sheet read, `whoami` where a due candidate exists, and
   no publication. A no-due dry run exercises authentication parsing but
   may skip the paid X API identity call.
5. For first real cloud post: explicitly select a **fresh, future-scheduled,
   approved** low-risk candidate. Keep scheduler disabled. After explicit
   operator authorization set
   `EDITORIAL_ECON_RUNTIME_PROMOTED=true`,
   `EDITORIAL_ECON_PUBLISH_ENABLED=true`,
   `EDITORIAL_ARGENTINA_ECON_PUBLISHER_DISABLED=0` and dispatch apply once.
6. Verify exact X URL and both QUEUE/DRAFTS writebacks and clear any
   `PUBLISHING` uncertainty before another run.
7. Only after that, set `EDITORIAL_ECON_SCHEDULER_ENABLED=true`.
   Turn off local economics publication timers; ModernAIDev remains untouched.

**Stop quickly:** set `EDITORIAL_ARGENTINA_ECON_PUBLISHER_DISABLED=1`.
No high-frequency October 8 pilot flags are used in Actions.

## Account-wide duplicate and cadence protection

The existing Sheet and X history checks continue to govern publication.
GitHub Actions `concurrency` serializes this workflow only; it cannot
serialize a separately running local publisher. The Sheet PUBLISHING state
must be reconciled before any new mutation. A missed slot is skipped,
not caught up en masse.

## Known tradeoff

OAuth1 removes rotating-token state, but token revocation and permission
changes still require reauthorization. Keep the static economics
credential limited to the existing economics account/app. A X API
identity-mismatch blocks before posting.
