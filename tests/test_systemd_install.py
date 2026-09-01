from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "src/office_runtime/scripts/install_systemd.py"
UNIT_NAMES = (
    "office-compile.service",
    "office-compile.timer",
    "staff-briefs.service",
    "staff-briefs.timer",
    "evidence-daily.service",
    "evidence-daily.timer",
)


class SystemdInstallTests(unittest.TestCase):
    def test_tracked_services_are_machine_neutral(self) -> None:
        for path in sorted((ROOT / "systemd/user").glob("*.service")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("/home/matias/", text)
            self.assertNotIn("@@", text)
            self.assertIn("runtime.env", text)
            self.assertIn("systemd_entrypoint.sh", text)

    def test_render_from_arbitrary_checkout_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rendered"
            command = [
                sys.executable,
                str(INSTALLER),
                "render",
                "--repo-root",
                str(ROOT),
                "--python-bin",
                sys.executable,
                "--evidence-root",
                str(ROOT),
                "--out",
                str(out),
            ]
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            subprocess.run(command, check=True, cwd=ROOT, env=env, capture_output=True, text=True)

            unit_dir = out / "units"
            self.assertEqual({path.name for path in unit_dir.iterdir()}, set(UNIT_NAMES))
            runtime_env = (out / "runtime.env").read_text(encoding="utf-8")
            self.assertIn(f'OFFICE_ROOT="{ROOT}"', runtime_env)
            self.assertIn(f'OFFICE_PYTHON="{Path(sys.executable).resolve()}"', runtime_env)
            self.assertIn(f'OFFICE_EVIDENCE_ROOTS="{ROOT}"', runtime_env)

            for name in UNIT_NAMES:
                text = (unit_dir / name).read_text(encoding="utf-8")
                self.assertNotIn("/home/matias/", text)
                self.assertNotIn("@@", text)

            analyzer = shutil.which("systemd-analyze")
            if analyzer:
                subprocess.run(
                    [analyzer, "verify", *(str(unit_dir / name) for name in UNIT_NAMES)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

    def test_relative_repo_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            command = [
                sys.executable,
                str(INSTALLER),
                "render",
                "--repo-root",
                ".",
                "--python-bin",
                sys.executable,
                "--evidence-root",
                str(ROOT),
                "--out",
                tmp,
            ]
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("repo root must be an absolute path", result.stderr)


if __name__ == "__main__":
    unittest.main()
