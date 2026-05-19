from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name, "").strip()
    return v if v else default

@dataclass(frozen=True)
class OfficeConfig:
    service_account_json: str
    spreadsheet_id: str
    front_gid: str
    carry_gid: str
    runtime_gid: str
    support_gid: str
    out_root: Path
    scripts_dir: Path
    strict: bool

    @property
    def latest_dir(self) -> Path:
        return self.out_root / "latest"

    @property
    def runs_dir(self) -> Path:
        return self.out_root / "runs"

def load_config() -> OfficeConfig:
    root = Path(_env("OFFICE_ROOT", ".")).resolve()
    out_root = Path(_env("OFFICE_OUT_ROOT", str(root / "artifacts"))).resolve()
    return OfficeConfig(
        service_account_json=_env("GOOGLE_APPLICATION_CREDENTIALS", str(root / "newgsheets-349817-cdd6efdaa76f.json")),
        spreadsheet_id=_env("OFFICE_SPREADSHEET_ID", "1mImijqIwcbBqcO05xKzPWMITo-53ypjd1BEGicTp3jE"),
        front_gid=_env("OFFICE_FRONT_GID", "716143116"),
        carry_gid=_env("OFFICE_CARRY_GID", "1585724687"),
        runtime_gid=_env("OFFICE_RUNTIME_GID", "1395426441"),
        support_gid=_env("OFFICE_SUPPORT_GID", "788211576"),
        out_root=out_root,
        scripts_dir=Path(_env("OFFICE_SCRIPTS_DIR", str(root / "src" / "office_runtime" / "scripts"))).resolve(),
        strict=_env("OFFICE_STRICT", "false").lower() == "true",
    )
