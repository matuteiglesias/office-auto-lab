from __future__ import annotations
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def _sheets_service(service_account_json: str):
    creds = Credentials.from_service_account_file(service_account_json, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)

def _sheet_title_from_gid(service, spreadsheet_id: str, gid: str) -> str:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sh in meta.get("sheets", []):
        props = sh.get("properties", {})
        if str(props.get("sheetId")) == str(gid):
            return props["title"]
    raise ValueError(f"Could not find sheet with gid={gid}")

def _dedupe_columns(cols):
    seen = {}
    out = []
    for c in cols:
        base = str(c).strip() if str(c).strip() else "unnamed"
        n = seen.get(base, 0)
        out.append(base if n == 0 else f"{base}__{n}")
        seen[base] = n + 1
    return out

def read_sheet_values(service_account_json: str, spreadsheet_id: str, gid: str) -> pd.DataFrame:
    service = _sheets_service(service_account_json)
    title = _sheet_title_from_gid(service, spreadsheet_id, gid)
    rng = f"'{title}'!A:ZZ"
    res = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=rng
    ).execute()
    values = res.get("values", [])
    if not values:
        return pd.DataFrame()
    header = _dedupe_columns(values[0])
    rows = values[1:]
    width = len(header)
    norm = [(row + [""] * (width - len(row)))[:width] for row in rows]
    df = pd.DataFrame(norm, columns=header).fillna("")
    return df

def coerce_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y", "x"])

def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = _dedupe_columns(df.columns)
    for i in range(len(df.columns)):
        df.iloc[:, i] = df.iloc[:, i].astype(str).str.strip()
    return df.fillna("")

def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def promote_latest(run_dir: Path, latest_dir: Path) -> None:
    latest_dir.mkdir(parents=True, exist_ok=True)
    for p in latest_dir.iterdir():
        if p.is_file() or p.is_symlink():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)
    for p in run_dir.iterdir():
        dest = latest_dir / p.name
        if p.is_dir():
            shutil.copytree(p, dest)
        else:
            shutil.copy2(p, dest)

def head_link_candidates(row: dict) -> list[str]:
    keys = [k for k in row if "link" in k.lower() or "path" in k.lower() or "slug" in k.lower()]
    vals = []
    for k in keys:
        v = str(row.get(k, "")).strip()
        if v:
            vals.append(f"{k}: {v}")
    return vals[:6]

def is_http_url(s: str) -> bool:
    s = str(s).strip().lower()
    return s.startswith("http://") or s.startswith("https://")

def check_http(url: str) -> tuple[bool, str]:
    try:
        r = requests.head(url, allow_redirects=True, timeout=10)
        if r.status_code >= 400:
            r = requests.get(url, allow_redirects=True, timeout=10)
        return (r.status_code < 400, str(r.status_code))
    except Exception as e:
        return (False, type(e).__name__)
