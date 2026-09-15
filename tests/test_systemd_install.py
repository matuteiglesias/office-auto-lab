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
    "office-v2-generation.service",
    "office-v2-generation.timer",
)


class SystemdInstallTests(unittest.TestCase):
    def test_tracked_services_are_machine_neutral(self) -> None:
        for path in sorted((ROOT / "systemd/user").glob("*.service")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("/home/matias/", text)
            self.assertNotIn("@@", text)
            self.assertIn("runtime.env", text)
            self.assertIn("systemd_entrypoint.sh", text)

    def test_v2_timer_is_one_coherent_office_clock(self) -> None:
        timer = (ROOT / "systemd/user/office-v2-generation.timer").read_text(encoding="utf-8")
        self.assertEqual(timer.count("OnCalendar="), 4)
        for time in ("08:05:00", "12:05:00", "16:05:00", "20:05:00"):
            self.assertIn(f"OnCalendar=*-*-* {time}", timer)
        self.assertIn("Persistent=true", timer)

        service = (ROOT / "systemd/user/office-v2-generation.service").read_text(encoding="utf-8")
        self.assertIn("systemd_entrypoint.sh\" office-v2-generation", service)
        self.assertNotIn("staff-briefs", service)
        self.assertNotIn("After=", service)
        self.assertNotIn("Requires=", service)

    def test_v2_adapter_is_fail_closed_until_m8_command_is_available(self) -> None:
        entrypoint = (ROOT / "src/office_runtime/scripts/systemd_entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("office-v2-generation", entrypoint)
        self.assertIn("another generation is running", entrypoint)
        self.assertIn("awaiting the canonical M8 runtime command", entrypoint)
        self.assertNotIn("office-v2-generation)\n    exec", entrypoint)

    def test_legacy_units_remain_tracked_during_migration(self) -> None:
        for name in ("office-compile.service", "office-compile.timer", "staff-briefs.service", "staff-briefs.timer"):
            self.assertTrue((ROOT / "systemd/user" / name).is_file())

    def test_v2_is_not_enabled_by_legacy_enable_flag(self) -> None:
        installer_source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('if args.enable_v2:', installer_source)
        self.assertIn('V2_TIMER_NAMES', installer_source)
        enable_block = installer_source.split('if args.enable:', 1)[1].split('if args.enable_v2:', 1)[0]
        self.assertNotIn('V2_TIMER_NAMES', enable_block)

    def test_service_does_not_swallow_failures(self) -> None:
        entrypoint = (ROOT / "src/office_runtime/scripts/systemd_entrypoint.sh").read_text(encoding="utf-8")
        service = (ROOT / "systemd/user/office-v2-generation.service").read_text(encoding="utf-8")
        self.assertNotIn("|| true", service)
        self.assertNotIn("|| true", entrypoint)
        self.assertIn("set -euo pipefail", entrypoint)

    def test_render_from_arbitrary_checkout_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / "rendered"
            repo_context = tmp_path / "repo-context.json"
            surface_context = tmp_path / "surfaces.json"
            repo_context.write_text('{"contract":"context:github-repositories@1","repositories":{}}', encoding="utf-8")
            surface_context.write_text('{"contract":"registry:estate-surfaces@1","surfaces":[]}', encoding="utf-8")
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
                "--repo-context-json",
                str(repo_context),
                "--surface-context-json",
                str(surface_context),
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
            self.assertIn(f'OFFICE_REPO_CONTEXT_JSON="{repo_context.resolve()}"', runtime_env)
            self.assertIn(f'OFFICE_SURFACE_CONTEXT_JSON="{surface_context.resolve()}"', runtime_env)

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

    def test_optional_contexts_are_omitted_when_not_configured(self) -> None:
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
            runtime_env = (out / "runtime.env").read_text(encoding="utf-8")
            self.assertNotIn("OFFICE_REPO_CONTEXT_JSON", runtime_env)
            self.assertNotIn("OFFICE_SURFACE_CONTEXT_JSON", runtime_env)

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

    def test_missing_surface_context_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-surfaces.json"
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
                "--surface-context-json",
                str(missing),
                "--out",
                str(Path(tmp) / "rendered"),
            ]
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("surface context JSON does not exist", result.stderr)

    def test_context_path_must_be_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
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
                "--surface-context-json",
                "surfaces.json",
                "--out",
                str(Path(tmp) / "rendered"),
            ]
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("surface context JSON must be an absolute path", result.stderr)


if __name__ == "__main__":
    unittest.main()
