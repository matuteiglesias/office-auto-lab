# ModernAIDev curated manual inventory

**Status:** production bounded operator inventory
**Audience:** Editorial operators and maintainers
**Owner:** office-auto-lab Editorial
**Verified against:** PR #83

ModernAIDev retains independent X account identity, OAuth1 credential, and editorial Sheet. The cloud publisher only considers `APPROVE` low-risk `CANDIDATES`/`QUEUE` pairs due within twelve hours and never exceeds one publication per twenty-four hours. `forced_pipeline_acceptance` remains unpublishable.

The early October publisher was restricted to a three-ID acceptance allowlist. For an operator-curated ongoing inventory, `authorized_candidate_ids` is now empty, while `require_manual_seed=true` remains in force. Only individually curated candidates with `quality_summary.manual_seed=true`, explicit `APPROVE`, and a due timestamp may publish. Generated, unapproved, high-risk or expired content stays blocked.

This is a bounded bridge for verified evergreen material, not authorization to auto-approve arbitrary LLM output. New ideas must preserve source URLs and be reviewed before authorization. Publishing receipts and the read-only daily health job distinguish delivered posts from green-but-empty jobs.
