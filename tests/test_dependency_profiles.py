from __future__ import annotations

import sys
import unittest
from pathlib import Path

from office_runtime.dependencies import (
    ACTIVE_PROFILES,
    CONSTRAINTS_PATH,
    PROFILE_PATHS,
    install_command,
    load_constraints,
    load_profile,
    validate_profiles,
)


ROOT = Path(__file__).resolve().parents[1]


class DependencyProfileTests(unittest.TestCase):
    def test_profiles_validate_and_active_full_is_exact_union(self) -> None:
        validate_profiles(ROOT)
        loaded = {name: set(load_profile(ROOT, name)) for name in PROFILE_PATHS}
        expected = loaded["office"] | loaded["capture"] | loaded["repo-health"]
        self.assertEqual(loaded["full"], expected)
        self.assertEqual(ACTIVE_PROFILES, ("office", "capture", "repo-health", "full"))

    def test_constraints_are_exact_and_cover_every_profile(self) -> None:
        constraints = load_constraints(ROOT)
        self.assertIn("pandas", constraints)
        self.assertIn("openai", constraints)
        for profile in PROFILE_PATHS:
            self.assertTrue(set(load_profile(ROOT, profile)).issubset(constraints))

    def test_install_command_always_uses_constraints_and_one_profile(self) -> None:
        command = install_command(ROOT, "repo-health")
        self.assertEqual(command[:4], [sys.executable, "-m", "pip", "install"])
        self.assertEqual(command[4:6], ["-c", str(ROOT / CONSTRAINTS_PATH)])
        self.assertEqual(command[6:], ["-r", str(ROOT / PROFILE_PATHS["repo-health"])])

    def test_root_requirement_files_are_compatibility_shims(self) -> None:
        expected = {
            "requirements.txt": "full",
            "requirements-repo-health.txt": "repo-health",
            "requirements-auto-checker.txt": "legacy-auto-checker",
        }
        for filename, profile in expected.items():
            lines = [
                line.strip()
                for line in (ROOT / filename).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            self.assertEqual(
                lines,
                [
                    "-c requirements/constraints.txt",
                    f"-r requirements/profiles/{profile}.txt",
                ],
            )


if __name__ == "__main__":
    unittest.main()
