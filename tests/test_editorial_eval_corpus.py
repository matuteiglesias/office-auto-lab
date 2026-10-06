from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "editorial_v1" / "eval_corpus.json"


class EditorialEvalCorpusTests(unittest.TestCase):
    def test_required_semantic_cases_are_present(self) -> None:
        payload = json.loads(CORPUS.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "office_runtime.editorial.eval_corpus.v1")
        cases = {case["case_id"]: case for case in payload["cases"]}
        self.assertEqual(
            set(cases),
            {
                "strong_technical_pr",
                "trivial_dependency_pr",
                "security_credential_cleanup",
                "related_pr_synthesis",
                "in_progress_truth",
                "semantic_dedupe",
                "evidence_shortage",
            },
        )
        self.assertTrue(all(case.get("expected", {}).get("property") for case in cases.values()))


if __name__ == "__main__":
    unittest.main()
