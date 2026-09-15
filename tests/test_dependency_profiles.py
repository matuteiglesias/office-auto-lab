from __future__ import annotations

import unittest
from pathlib import Path

from office_runtime.dependencies import (
    ACTIVE_PROFILES,
    CONSTRAINTS_PATH,
    CORE_PROFILES,
    PROFILE_PATHS,
    SIDECAR_PROFILES,
    TEST_TOOLING_PATH,
    load_constraints,
    load_profile,
    load_test_tooling,
    validate_profiles,
)


ROOT = Path(__file__).resolve().parents[1]


class DependencyProfileTests(unittest.TestCase):
    def test_profiles_validate_and_full_is_exact_active_union(self) -> None:
        validate_profiles(ROOT)
        loaded = {name: set(load_profile(ROOT, name)) for name in PROFILE_PATHS}
        expected = loaded["office"] | loaded["capture"]
        self.assertEqual(loaded["full"], expected)
        self.assertEqual(CORE_PROFILES, ("office",))
        self.assertEqual(SIDECAR_PROFILES, ("capture",))
        self.assertEqual(ACTIVE_PROFILES, ("office", "capture", "full"))
        self.assertEqual(set(PROFILE_PATHS), {"office", "capture", "full"})

    def test_constraints_are_exact_and_cover_every_declared_surface(self) -> None:
        constraints = load_constraints(ROOT)
        self.assertIn("pandas", constraints)
        self.assertIn("openai", constraints)
        self.assertIn("pytest", constraints)
        for profile in PROFILE_PATHS:
            self.assertTrue(set(load_profile(ROOT, profile)).issubset(constraints))
        self.assertTrue(set(load_test_tooling(ROOT)).issubset(constraints))

    def test_test_tooling_is_not_runtime_profile_membership(self) -> None:
        tooling = set(load_test_tooling(ROOT))
        self.assertEqual(tooling, {"pytest"})
        runtime_packages = set().union(*(set(load_profile(ROOT, name)) for name in ACTIVE_PROFILES))
        self.assertTrue(tooling.isdisjoint(runtime_packages))
        self.assertEqual(TEST_TOOLING_PATH, Path("requirements/test.txt"))

    def test_root_requirements_is_only_supported_runtime_shim(self) -> None:
        lines = [
            line.strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            lines,
            [
                "-c requirements/constraints.txt",
                "-r requirements/profiles/full.txt",
            ],
        )
        self.assertFalse((ROOT / "requirements-repo-health.txt").exists())
        self.assertFalse((ROOT / "requirements-auto-checker.txt").exists())
        self.assertTrue((ROOT / CONSTRAINTS_PATH).is_file())


if __name__ == "__main__":
    unittest.main()
