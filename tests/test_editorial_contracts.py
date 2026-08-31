from __future__ import annotations

import unittest

from office_runtime.editorial.contracts import (
    CANDIDATE_SCHEMA,
    ContractError,
    load_projection_profiles,
    validate_candidate,
)


class EditorialProjectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profiles = load_projection_profiles()

    def test_dual_projection_profiles_are_explicit(self) -> None:
        self.assertEqual(set(self.profiles), {"dev", "argentina_econ"})
        self.assertEqual(self.profiles["dev"]["strategy"], "dev_projection")
        self.assertEqual(self.profiles["argentina_econ"]["strategy"], "argentina_econ")
        self.assertEqual(
            self.profiles["argentina_econ"]["public_identity"]["x_handle"],
            "matuteiglesias",
        )

    def test_dev_candidate_requires_real_work_reference(self) -> None:
        candidate = {
            "schema_version": CANDIDATE_SCHEMA,
            "candidate_id": "dev-1",
            "profile_id": "dev",
            "text": "A public engineering lesson.",
            "risk_class": "low",
            "evidence_refs": ["https://github.com/example/repo/pull/1"],
            "work_refs": ["example/repo#1"],
        }
        self.assertEqual(validate_candidate(candidate, self.profiles["dev"]), candidate)

        broken = dict(candidate)
        broken.pop("work_refs")
        with self.assertRaises(ContractError):
            validate_candidate(broken, self.profiles["dev"])

    def test_argentina_econ_requires_claim_evidence_idea_triangle(self) -> None:
        candidate = {
            "schema_version": CANDIDATE_SCHEMA,
            "candidate_id": "econ-1",
            "profile_id": "argentina_econ",
            "text": "A current claim looks different in the longer-run data.",
            "risk_class": "low",
            "evidence_refs": ["https://example.com/current-claim", "https://example.com/plot"],
            "current_claim_ref": "media:item:123",
            "owned_evidence_refs": ["atlas:plot:external-constraint-01"],
            "approved_idea_refs": ["idea:external-constraint-01"],
            "relation": "historicizes",
        }
        self.assertEqual(
            validate_candidate(candidate, self.profiles["argentina_econ"]), candidate
        )

        for required in ("current_claim_ref", "owned_evidence_refs", "approved_idea_refs"):
            broken = dict(candidate)
            broken.pop(required)
            with self.assertRaises(ContractError):
                validate_candidate(broken, self.profiles["argentina_econ"])

    def test_cannot_adjudicate_never_becomes_publishable_copy(self) -> None:
        candidate = {
            "schema_version": CANDIDATE_SCHEMA,
            "candidate_id": "econ-skip",
            "profile_id": "argentina_econ",
            "text": "No grounded adjudication is available.",
            "risk_class": "low",
            "evidence_refs": ["https://example.com/current-claim"],
            "current_claim_ref": "media:item:456",
            "owned_evidence_refs": ["atlas:search:no-match"],
            "approved_idea_refs": ["idea:search:no-match"],
            "relation": "cannot_adjudicate",
        }
        with self.assertRaises(ContractError):
            validate_candidate(candidate, self.profiles["argentina_econ"])


if __name__ == "__main__":
    unittest.main()
