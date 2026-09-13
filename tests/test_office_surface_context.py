import tempfile
import unittest
from pathlib import Path

import pandas as pd

from office_runtime.office.render import render_office_summary
from office_runtime.office.surface_context import load_surface_context, summarize_surface_context


class OfficeSurfaceContextTests(unittest.TestCase):
    def test_missing_surface_context_is_nonfatal(self):
        summary = summarize_surface_context(None)
        self.assertFalse(summary["configured"])
        self.assertEqual(summary["surface_count"], 0)
        self.assertEqual(summary["candidate_ids"], [])
        self.assertEqual(summary["remediation_ids"], [])

    def test_surface_context_summary_is_advisory_and_bounded(self):
        payload = {
            "contract": "registry:estate-surfaces@1",
            "surfaces": [
                {
                    "id": "surface.authority",
                    "lifecycle": "active",
                    "kind": "human_state",
                    "authority": {"state": "canonical"},
                    "promotion": {"state": "promoted"},
                },
                {
                    "id": "surface.projection",
                    "lifecycle": "active",
                    "kind": "projection",
                    "authority": {"state": "projection_only"},
                    "promotion": {"state": "promoted"},
                },
                {
                    "id": "surface.candidate",
                    "lifecycle": "candidate",
                    "kind": "proposal_surface",
                    "authority": {"state": "proposal_only"},
                    "promotion": {"state": "candidate"},
                },
                {
                    "id": "surface.remediation",
                    "lifecycle": "active",
                    "kind": "remediation_queue",
                    "authority": {"state": "noncanonical"},
                    "promotion": {"state": "remediation"},
                },
            ],
        }
        summary = summarize_surface_context(payload)
        self.assertTrue(summary["configured"])
        self.assertEqual(summary["surface_count"], 4)
        self.assertEqual(summary["active_count"], 3)
        self.assertEqual(summary["promoted_count"], 2)
        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(summary["remediation_count"], 1)
        self.assertEqual(summary["canonical_count"], 1)
        self.assertEqual(summary["projection_count"], 1)
        self.assertEqual(summary["candidate_ids"], ["surface.candidate"])
        self.assertEqual(summary["remediation_ids"], ["surface.remediation"])

    def test_load_surface_context_validates_contract_and_unique_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "surfaces.json"
            path.write_text(
                '{"contract":"registry:estate-surfaces@1","surfaces":[{"id":"surface.one"}]}',
                encoding="utf-8",
            )
            payload = load_surface_context(path)
            self.assertEqual(payload["surfaces"][0]["id"], "surface.one")

            path.write_text(
                '{"contract":"registry:estate-surfaces@1","surfaces":[{"id":"surface.one"},{"id":"surface.one"}]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate surface ids"):
                load_surface_context(path)

    def test_wrong_surface_context_contract_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "surfaces.json"
            path.write_text('{"contract":"wrong","surfaces":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected surface context contract"):
                load_surface_context(path)

    def test_office_summary_renders_candidates_and_remediation_without_routing(self):
        manifest = {
            "row_counts": {},
            "surface_context": {
                "configured": True,
                "surface_count": 4,
                "active_count": 3,
                "promoted_count": 2,
                "candidate_count": 1,
                "remediation_count": 1,
                "canonical_count": 1,
                "projection_count": 1,
                "candidate_ids": ["surface.candidate"],
                "remediation_ids": ["surface.remediation"],
            },
        }
        empty = pd.DataFrame()
        text = render_office_summary(manifest, empty, empty, empty, empty, empty, empty, [])
        self.assertIn("## Estate Surface Context", text)
        self.assertIn("surface.candidate", text)
        self.assertIn("surface.remediation", text)
        self.assertIn("advisory only", text)


if __name__ == "__main__":
    unittest.main()
