from __future__ import annotations

import unittest

from office_runtime.editorial.intelligence.batch import (
    BatchConfig,
    FallbackPool,
    compile_daily_batch,
    failed_daily_batch,
)


def candidate(
    number: int,
    *,
    claim: str | None = None,
    source: str | None = None,
    repo: str | None = None,
    family: str = "lesson",
    fingerprint: str | None = None,
    expires_at: str | None = None,
    source_tier: str = "fresh",
) -> dict:
    text = claim or f"Distinct engineering lesson number {number} about bounded reliability mechanism {number}."
    value = {
        "candidate_id": f"cand:{number}",
        "text": text,
        "claim": text,
        "candidate_family": family,
        "semantic_fingerprint": fingerprint or f"sem:{number}",
        "evidence_refs": [source or f"ev:{number}"],
        "work_refs": [source or f"ev:{number}"],
        "source_event_refs": [source or f"ev:{number}"],
        "repository_refs": [repo or f"repo/{number % 3}"],
        "career_signals": [f"signal-{number % 3}"],
        "freshness_class": "recent",
        "generated_at": f"2026-10-06T12:{number:02d}:00Z",
        "expires_at": expires_at,
        "machine_disposition": "stage",
        "source_tier": source_tier,
        "quality": {
            "evidence": 4,
            "specificity": 4,
            "external_usefulness": 3,
            "novelty": 3,
            "professional_signal": 3,
        },
        "gates": {
            "disclosure_risk": "PASS",
            "repetition_risk": "PASS",
            "status_truth_risk": "PASS",
        },
    }
    return value


class EditorialBatchTests(unittest.TestCase):
    def test_defaults_hit_target_and_preserve_diversity_metadata(self) -> None:
        result = compile_daily_batch(
            primary_candidates=[candidate(i) for i in range(1, 11)],
            batch_date="2026-10-06",
        )
        self.assertEqual(result.batch["inventory_status"], "HEALTHY")
        self.assertEqual(len(result.selected_candidates), 8)
        self.assertLessEqual(len(result.selected_candidates), result.batch["ceiling_count"])
        self.assertGreater(len(result.batch["diversity_summary"]["repository_refs"]), 1)
        self.assertEqual(result.fallback_requests, ())

    def test_source_event_concentration_is_capped_at_two(self) -> None:
        pool = [candidate(i, source="github:repo:pr:7") for i in range(1, 7)]
        result = compile_daily_batch(primary_candidates=pool, batch_date="2026-10-06")
        self.assertEqual(len(result.selected_candidates), 2)
        self.assertEqual(result.batch["inventory_status"], "DEGRADED_INVENTORY")
        self.assertTrue(any(item["reason"] == "source_concentration" for item in result.rejected))

    def test_near_duplicate_and_recent_fingerprint_are_suppressed(self) -> None:
        same_claim = "Retries should preserve failure provenance across system boundaries."
        primary = [
            candidate(1, claim=same_claim, fingerprint="sem:first"),
            candidate(2, claim=same_claim + " Always.", fingerprint="sem:second"),
            candidate(3, claim="A separate lesson about deterministic evidence validation."),
        ]
        history = [candidate(99, fingerprint="sem:history", claim="A prior unrelated observation.")]
        primary.append(candidate(4, fingerprint="sem:history", claim="Different wording but same semantic identity."))
        result = compile_daily_batch(
            primary_candidates=primary,
            recent_history=history,
            batch_date="2026-10-06",
        )
        reasons = {item["reason"] for item in result.rejected}
        self.assertIn("near_duplicate", reasons)
        self.assertIn("recent_fingerprint_repeat", reasons)

    def test_fallback_widens_boundedly_without_fabricating(self) -> None:
        primary = [candidate(1), candidate(2)]
        recent = [candidate(3, source_tier="recent14"), candidate(4, source_tier="recent14")]
        synthesis = [candidate(5, family="synthesis", source_tier="synthesis")]
        result = compile_daily_batch(
            primary_candidates=primary,
            fallback_pools=[
                FallbackPool("recent_14d", recent),
                FallbackPool("cross_project_synthesis", synthesis),
            ],
            batch_date="2026-10-06",
        )
        self.assertEqual(result.batch["inventory_status"], "HEALTHY")
        self.assertEqual(len(result.selected_candidates), 5)
        self.assertEqual(result.fallback_requests, ("recent_14d", "cross_project_synthesis"))

    def test_shortage_is_degraded_after_fallbacks_exhaust(self) -> None:
        result = compile_daily_batch(
            primary_candidates=[candidate(1), candidate(2)],
            fallback_pools=[FallbackPool("recent_14d", [candidate(3)])],
            batch_date="2026-10-06",
        )
        self.assertEqual(result.batch["inventory_status"], "DEGRADED_INVENTORY")
        self.assertEqual(len(result.selected_candidates), 3)
        self.assertIn("eligible_fallback_pools_exhausted", result.batch["shortage_reasons"][1])

    def test_expired_candidate_is_not_selected(self) -> None:
        result = compile_daily_batch(
            primary_candidates=[candidate(1, expires_at="2026-10-05T23:59:00Z")],
            batch_date="2026-10-06",
        )
        self.assertEqual(result.selected_candidates, ())
        self.assertEqual(result.rejected[0]["reason"], "expired")

    def test_fatal_failure_is_distinct_from_inventory_shortage(self) -> None:
        result = failed_daily_batch(
            batch_date="2026-10-06",
            reason="model_contract_failure",
        )
        self.assertEqual(result.batch["inventory_status"], "FAILED")
        self.assertEqual(result.batch["candidate_ids"], [])
        self.assertEqual(result.batch["shortage_reasons"], ["fatal:model_contract_failure"])
        self.assertEqual(result.selected_candidates, ())

    def test_ceiling_and_invalid_config_are_deterministic(self) -> None:
        config = BatchConfig(target=12, floor=5, ceiling=12)
        result = compile_daily_batch(
            primary_candidates=[candidate(i) for i in range(1, 20)],
            batch_date="2026-10-06",
            config=config,
        )
        self.assertEqual(len(result.selected_candidates), 12)
        with self.assertRaises(ValueError):
            compile_daily_batch(
                primary_candidates=[],
                batch_date="2026-10-06",
                config=BatchConfig(target=4, floor=5, ceiling=12),
            )


if __name__ == "__main__":
    unittest.main()
