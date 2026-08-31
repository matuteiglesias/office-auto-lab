#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


UNIT_NAMES = (
    "office-compile.service",
    "office-compile.timer",
    "staff-briefs.service",
    "staff-briefs.timer",
    "evidence-daily.service",
    "evidence-daily.timer",
)
TIMER_NAMES = tuple(name for name in UNIT_NAMES if name.endswith(".timer"))
RUNTIME_ENV_PATH = Path.home() / ".config/office-auto-lab/runtime.env"


class InstallError(ValueError):
    pass


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def _absolute_existing(path: Path, label: str, *, executable: bool = False) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        raise InstallError(f"{label} must be an absolute path: {path}")
    resolved = path.resolve()
    if not resolved.exists():
        raise InstallError(f"{label} does not exist: {resolved}")
    if executable and (not resolved.is_file() or not os.access(resolved, os.X_OK)):
        raise InstallError(f"{label} must be an executable file: {resolved}")
    return resolved


def validate_configuration(repo_root: Path, python_bin: Path, evidence_roots: list[Path]) -> tuple[Path, Path, list[Path]]:
    root = _absolute_existing(repo_root, "repo root")
    python = _absolute_existing(python_bin, "Python executable", executable=True)
    required = (
        root / "src/office_runtime/scripts/office_run.sh",
        root / "src/office_runtime/scripts/systemd_entrypoint.sh",
        root / "systemd/user",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise InstallError(f"repo root is missing required runtime paths: {missing}")
    if not evidence_roots:
        raise InstallError("at least one --evidence-root is required")
    roots: list[Path] = []
    for value in evidence_roots:
        resolved = _absolute_existing(value, "evidence root")
        if ":" in str(resolved):
            raise InstallError(f"evidence roots may not contain ':' because it is the runtime separator: {resolved}")
        roots.append(resolved)
    return root, python, roots


def _env_quote(value: str) -> str:
    if "\n" in value or "\r" in value or "\x00" in value:
        raise InstallError("runtime environment values may not contain newlines or NUL bytes")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def runtime_env(repo_root: Path, python_bin: Path, evidence_roots: list[Path], evidence_out_root: str) -> str:
    values = {
        "OFFICE_ROOT": str(repo_root),
        "OFFICE_PYTHON": str(python_bin),
        "OFFICE_EVIDENCE_ROOTS": ":".join(str(path) for path in evidence_roots),
        "OFFICE_EVIDENCE_OUT_ROOT": evidence_out_root,
    }
    return "\n".join(f"{key}={_env_quote(value)}" for key, value in values.items()) + "\n"


def validate_tracked_units(source_dir: Path) -> None:
    for name in UNIT_NAMES:
        path = source_dir / name
        if not path.is_file():
            raise InstallError(f"missing tracked systemd unit: {path}")
        text = path.read_text(encoding="utf-8")
        if "/home/matias/" in text:
            raise InstallError(f"tracked unit still contains machine-specific home path: {path}")
        if "@@" in text:
            raise InstallError(f"tracked unit contains unresolved template marker: {path}")


def render(*, repo_root: Path, python_bin: Path, evidence_roots: list[Path], unit_dir: Path, env_path: Path,
           evidence_out_root: str = "artifacts/evidence") -> None:
    root, python, roots = validate_configuration(repo_root, python_bin, evidence_roots)
    source_dir = root / "systemd/user"
    validate_tracked_units(source_dir)
    unit_dir.mkdir(parents=True, exist_ok=True)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    for name in UNIT_NAMES:
        shutil.copyfile(source_dir / name, unit_dir / name)
    env_path.write_text(runtime_env(root, python, roots, evidence_out_root), encoding="utf-8")


def _systemctl(*args: str, check: bool = True) -> None:
    subprocess.run(["systemctl", "--user", *args], check=check)


def install(args: argparse.Namespace) -> int:
    unit_dir = args.unit_dir or (Path.home() / ".config/systemd/user")
    render(
        repo_root=args.repo_root,
        python_bin=args.python_bin,
        evidence_roots=args.evidence_root,
        unit_dir=unit_dir,
        env_path=RUNTIME_ENV_PATH,
        evidence_out_root=args.evidence_out_root,
    )
    _systemctl("daemon-reload")
    if args.enable:
        _systemctl("enable", "--now", *TIMER_NAMES)
    print(f"installed units: {unit_dir}")
    print(f"runtime environment: {RUNTIME_ENV_PATH}")
    return 0


def render_only(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    render(
        repo_root=args.repo_root,
        python_bin=args.python_bin,
        evidence_roots=args.evidence_root,
        unit_dir=out / "units",
        env_path=out / "runtime.env",
        evidence_out_root=args.evidence_out_root,
    )
    print(out)
    return 0


def uninstall(args: argparse.Namespace) -> int:
    unit_dir = args.unit_dir or (Path.home() / ".config/systemd/user")
    _systemctl("disable", "--now", *TIMER_NAMES, check=False)
    for name in UNIT_NAMES:
        (unit_dir / name).unlink(missing_ok=True)
    _systemctl("daemon-reload", check=False)
    if args.purge_config:
        RUNTIME_ENV_PATH.unlink(missing_ok=True)
    print(f"removed Office Runtime units from {unit_dir}")
    return 0


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--python-bin", type=Path, default=Path(sys.executable))
    parser.add_argument("--evidence-root", action="append", type=Path, required=True)
    parser.add_argument("--evidence-out-root", default="artifacts/evidence")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render/install portable Office Runtime user systemd units.")
    sub = parser.add_subparsers(dest="command", required=True)

    render_parser = sub.add_parser("render", help="Render units and runtime.env without mutating systemd state.")
    _add_runtime_args(render_parser)
    render_parser.add_argument("--out", required=True, type=Path)
    render_parser.set_defaults(handler=render_only)

    install_parser = sub.add_parser("install", help="Install units for the current user.")
    _add_runtime_args(install_parser)
    install_parser.add_argument("--unit-dir", type=Path, default=None)
    install_parser.add_argument("--enable", action="store_true", help="Enable and start all tracked timers after install.")
    install_parser.set_defaults(handler=install)

    uninstall_parser = sub.add_parser("uninstall", help="Disable and remove installed Office Runtime user units.")
    uninstall_parser.add_argument("--unit-dir", type=Path, default=None)
    uninstall_parser.add_argument("--purge-config", action="store_true")
    uninstall_parser.set_defaults(handler=uninstall)

    args = parser.parse_args()
    try:
        return args.handler(args)
    except InstallError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
