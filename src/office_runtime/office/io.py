from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _sheets_service(service_account_json: str):
    creds = Credentials.from_service_account_file(service_account_json, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _sheet_title_from_gid(service, spreadsheet_id: str, gid: str) -> str:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        if str(props.get("sheetId")) == str(gid):
            return props["title"]
    raise ValueError(f"Could not find sheet with gid={gid}")


def _dedupe_columns(columns) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for column in columns:
        base = str(column).strip() or "unnamed"
        count = seen.get(base, 0)
        out.append(base if count == 0 else f"{base}__{count}")
        seen[base] = count + 1
    return out


def read_sheet_values(service_account_json: str, spreadsheet_id: str, gid: str) -> pd.DataFrame:
    service = _sheets_service(service_account_json)
    title = _sheet_title_from_gid(service, spreadsheet_id, gid)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{title}'!A:ZZ",
    ).execute()
    values = result.get("values", [])
    if not values:
        return pd.DataFrame()
    header = _dedupe_columns(values[0])
    width = len(header)
    rows = [(row + [""] * (width - len(row)))[:width] for row in values[1:]]
    return pd.DataFrame(rows, columns=header).fillna("")


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame.columns = _dedupe_columns(frame.columns)
    for index in range(len(frame.columns)):
        frame.iloc[:, index] = frame.iloc[:, index].astype(str).str.strip()
    return frame.fillna("")


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
