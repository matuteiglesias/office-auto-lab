from __future__ import annotations

import unittest

from office_runtime.editorial.intelligence.adk_adapter import (
    AngleOutputModel,
    JudgeOutputModel,
    build_adk_editorial_intelligence,
)
from office_runtime.editorial.intelligence.interfaces import EditorialIntelligence


class EditorialAdkAdapterTests(unittest.TestCase):
    def test_structured_schemas_allow_abstention_without_provider_call(self) -> None:
        output = AngleOutputModel.model_validate({"angles": []})
        self.assertEqual(output.angles, [])
        judged = JudgeOutputModel.model_validate({"decisions": []})
        self.assertEqual(judged.decisions, [])

    def test_two_stage_adk_adapter_constructs_without_contacting_provider(self) -> None:
        engine = build_adk_editorial_intelligence(
            angle_model="gemini-2.5-flash",
            judge_model="gemini-2.5-flash",
        )
        self.assertIsInstance(engine, EditorialIntelligence)


if __name__ == "__main__":
    unittest.main()
