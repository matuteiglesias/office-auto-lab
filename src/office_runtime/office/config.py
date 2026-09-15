from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


@dataclass(frozen=True)
class OfficeConfig:
    service_account_json: str
    spreadsheet_id: str
    out_root: Path

    @property
    def latest_dir(self) -> Path:
        """Sidecar-compatible mutable output root.

        Canonical Office v2 itself publishes through `out_root / v2`; Capture
        may continue using `latest` independently until its artifact contract is
        migrated.
        """
        return self.out_root / "latest"

    @property
    def v2_dir(self) -> Path:
        return self.out_root / "v2"


def load_config() -> OfficeConfig:
    root = Path(_env("OFFICE_ROOT", ".")).resolve()
    out_root = Path(_env("OFFICE_OUT_ROOT", str(root / "artifacts"))).resolve()
    return OfficeConfig(
        service_account_json=_env(
            "GOOGLE_APPLICATION_CREDENTIALS",
            str(root / "newgsheets-349817-cdd6efdaa76f.json"),
        ),
        spreadsheet_id=_env(
            "OFFICE_SPREADSHEET_ID",
            "1mImijqIwcbBqcO05xKzPWMITo-53ypjd1BEGicTp3jE",
        ),
        out_root=out_root,
    )
