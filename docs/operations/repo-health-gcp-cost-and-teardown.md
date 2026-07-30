# Repo Health GCP cost, rollback, and teardown

**Status:** canonical procedure; provider commands unexecuted
**Audience:** authorized deployers and cost owners
**Owner:** GCP infrastructure maintainers
**Verified against:** `8fbf76a`

## Cost boundary

Terraform creates a mandatory USD 10 monthly budget with 50%, 90%, and 100%
thresholds. A budget alerts; it does not cap spend. Cost drivers are Cloud Run
execution, Artifact Registry storage, GCS objects, BigQuery storage/query, logs,
and monitoring. The first release has no Scheduler, so only explicit executions
should incur run cost.

Keep projects limited to one-to-three, remote reads bounded, run frequency manual,
BigQuery queries partition-filtered, and evidence retention explicit (30 days by
default). Confirm billing-budget evidence during acceptance.

## Rollback

A failed image/job change should revert Terraform/image inputs to the last
accepted digest and commit, plan the exact delta, and apply only after review.
Do not delete or mutate accepted run evidence to simulate rollback. There is no
accepted provider baseline yet, so repository state alone cannot name a deployed
rollback target.

## Protected teardown

`allow_destroy=false` protects evidence tables and prevents bucket force-destroy.
After exporting and verifying the evidence packet, the following commands are
**unexecuted** and require explicit approval:

```bash
terraform -chdir=infra/gcp plan -var='allow_destroy=true' -destroy -out=destroy.tfplan
terraform -chdir=infra/gcp show -json destroy.tfplan > destroy.tfplan.json
terraform -chdir=infra/gcp apply destroy.tfplan
```

Confirm the plan targets only managed resources and preserve plan/apply output.
After apply, verify the Cloud Run Job, runtime identity grants, bucket, dataset,
registry, metric/alert, and budget disposition. Confirm no Scheduler exists.
Terraform intentionally leaves enabled APIs enabled.

Stop if accepted evidence is not exported, destroy scope is unexpected, project
identity differs, or retention/legal needs are unresolved. Record teardown as
completed, retained intentionally, or blocked—never infer it from local state.
