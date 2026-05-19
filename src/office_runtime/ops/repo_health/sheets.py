# sheets.py
from __future__ import annotations

import random
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

Record = Dict[str, Any]


# -------------------------
# Auth
# -------------------------
def auth_gspread(sa_file: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    return gspread.authorize(creds)


# -------------------------
# Small utils
# -------------------------
def _chunk_list(xs: List[Any], chunk_size: int) -> Iterable[List[Any]]:
    for i in range(0, len(xs), chunk_size):
        yield xs[i : i + chunk_size]


def col_idx_to_letter(idx_1_based: int) -> str:
    """1-based column index -> A1 letter."""
    n = idx_1_based
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _sleep_backoff(attempt: int) -> None:
    # exponential backoff + jitter, capped
    backoff = min(60.0, (2 ** (attempt - 1))) + random.random() * 0.5
    time.sleep(backoff)


def _is_throttle(e: Exception) -> bool:
    msg = str(e).lower()
    return ("429" in msg) or ("quota" in msg) or ("rate" in msg) or ("resource has been exhausted" in msg)


def _get_or_create_ws(sh: gspread.Spreadsheet, sheet_name: str) -> gspread.Worksheet:
    try:
        return sh.worksheet(sheet_name)
    except Exception:
        # Create with minimal size; it will auto-expand on writes
        return sh.add_worksheet(title=sheet_name, rows=100, cols=26)


def _dedupe_header(header: List[str]) -> List[str]:
    """
    Sheets sometimes accumulate duplicate header names; convert to unique keys.
    Example: ["a","a"] -> ["a","a__2"]
    """
    seen = {}
    out = []
    for h in header:
        k = (h or "").strip()
        if not k:
            k = "col"
        if k not in seen:
            seen[k] = 1
            out.append(k)
        else:
            seen[k] += 1
            out.append(f"{k}__{seen[k]}")
    return out


def _values_batch_update(spreadsheet: gspread.Spreadsheet, data_blocks: List[Dict[str, Any]], *, chunk_size: int = 40) -> None:
    """
    data_blocks: [{"range": "Sheet!A2:D2", "values": [[...]]}, ...]
    Uses spreadsheet.values_batch_update with retries and chunking.
    """
    if not data_blocks:
        return

    for chunk in _chunk_list(data_blocks, chunk_size):
        body = {"valueInputOption": "RAW", "data": chunk}
        max_attempts = 6
        for attempt in range(1, max_attempts + 1):
            try:
                spreadsheet.values_batch_update(body)
                break
            except Exception as e:
                if _is_throttle(e):
                    _sleep_backoff(attempt)
                    continue
                # payload too big => reduce chunk size locally
                msg = str(e).lower()
                if ("request payload size" in msg) or ("request too large" in msg) or ("413" in msg):
                    if len(chunk) == 1:
                        raise
                    # retry this chunk with smaller chunk size
                    smaller = max(1, len(chunk) // 2)
                    _values_batch_update(spreadsheet, chunk, chunk_size=smaller)
                    break
                raise
        else:
            raise RuntimeError("values_batch_update failed after retries")


# -------------------------
# Reads
# -------------------------
def read_tab_records(sh: gspread.Spreadsheet, sheet_name: str) -> List[Record]:
    """
    1 API call: ws.get_all_values()
    Returns list[dict] keyed by header row.
    """
    ws = _get_or_create_ws(sh, sheet_name)
    all_vals = ws.get_all_values()
    if not all_vals:
        return []
    header = _dedupe_header(all_vals[0])
    rows = all_vals[1:]
    out: List[Record] = []
    for r in rows:
        rec = {}
        for i, col in enumerate(header):
            rec[col] = r[i] if i < len(r) else ""
        out.append(rec)
    return out


# -------------------------
# Header management
# -------------------------
def ensure_header_has_columns(
    sh: gspread.Spreadsheet,
    sheet_name: str,
    required_cols: Sequence[str],
) -> List[str]:
    """
    Ensures required columns exist in the header row, appending missing ones at the end.
    Costs:
      - 1 call to read header row (row_values(1))
      - optional 1 call to update header
    Returns updated header list.
    """
    ws = _get_or_create_ws(sh, sheet_name)
    header = ws.row_values(1)  # 1 API call
    header = [h.strip() for h in header] if header else []
    changed = False
    for c in required_cols:
        if c not in header:
            header.append(c)
            changed = True
    if changed:
        ws.update("A1", [header])  # 1 API call
        time.sleep(0.15)
    return header


# -------------------------
# Writes
# -------------------------
def write_tab_overwrite(
    sh: gspread.Spreadsheet,
    sheet_name: str,
    rows: List[Record],
    *,
    header_order: Optional[List[str]] = None,
) -> None:
    """
    Overwrite entire sheet with header + rows.
    Costs:
      - 1 call to clear
      - 1 call to values_update
    """
    ws = _get_or_create_ws(sh, sheet_name)

    if not rows and not header_order:
        # just clear
        ws.clear()
        return

    if header_order:
        header = header_order
    else:
        # stable-ish header order: union of keys, sorted
        keys = set()
        for r in rows:
            keys.update(r.keys())
        header = sorted(keys)

    matrix = [header]
    for r in rows:
        matrix.append([str(r.get(k, "")) if r.get(k, "") is not None else "" for k in header])

    # clear then bulk update
    ws.clear()
    ws.update("A1", matrix, value_input_option="RAW")


def append_rows(
    sh: gspread.Spreadsheet,
    sheet_name: str,
    rows: List[Record],
    *,
    header_order: Optional[List[str]] = None,
    chunk_size: int = 200,
) -> None:
    """
    Append dict rows to a sheet.
    Costs:
      - if header exists and contains all cols: 1 call per chunk via append_rows
      - if header needs extension: 1 call to update header, then append
    """
    if not rows:
        return

    ws = _get_or_create_ws(sh, sheet_name)
    header = ws.row_values(1)  # 1 API call
    header = [h.strip() for h in header] if header else []

    if not header:
        # First write: do it as a single bulk update instead of append calls
        if header_order:
            header = header_order
        else:
            keys = set()
            for r in rows:
                keys.update(r.keys())
            header = sorted(keys)

        matrix = [header]
        for r in rows:
            matrix.append([str(r.get(k, "")) if r.get(k, "") is not None else "" for k in header])

        ws.update("A1", matrix, value_input_option="RAW")
        return

    # Extend header if new columns appear (robustness)
    if header_order:
        desired_cols = list(header_order)
    else:
        desired_cols = list(header)

    keys = set(desired_cols)
    for r in rows:
        for k in r.keys():
            if k not in keys:
                desired_cols.append(k)
                keys.add(k)

    if desired_cols != header:
        ws.update("A1", [desired_cols], value_input_option="RAW")
        time.sleep(0.15)
        header = desired_cols

    # Convert to list-of-lists aligned to header
    lol: List[List[Any]] = []
    for r in rows:
        lol.append([str(r.get(k, "")) if r.get(k, "") is not None else "" for k in header])

    # Append in chunks with retries
    for chunk in _chunk_list(lol, chunk_size):
        max_attempts = 6
        for attempt in range(1, max_attempts + 1):
            try:
                ws.append_rows(chunk, value_input_option="RAW")
                break
            except Exception as e:
                if _is_throttle(e):
                    _sleep_backoff(attempt)
                    continue
                raise
        else:
            raise RuntimeError("append_rows failed after retries")


# -------------------------
# Targeted batch updates (Projects summary)
# -------------------------
def batch_update_cells_by_col(
    sh: gspread.Spreadsheet,
    sheet_name: str,
    updates: List[Record],
    *,
    key_col: str,
    cols: Sequence[str],
    chunk_size: int = 40,
) -> None:
    """
    Update only specific columns for rows matched by key_col (e.g., project_id).
    Designed for the Projects summary writeback.

    Strategy:
      - 1 call to get_all_values() for header + key->row mapping
      - 1..N values_batch_update calls (chunked) to update only a contiguous tail range

    NOTE: For maximum efficiency, ensure cols are appended contiguously at the end
    via ensure_header_has_columns(..., cols) BEFORE calling this.
    """
    if not updates:
        return

    ws = _get_or_create_ws(sh, sheet_name)
    all_vals = ws.get_all_values()  # 1 API call
    if not all_vals:
        raise RuntimeError(f"Sheet {sheet_name} is empty; cannot batch-update by key.")

    header = [h.strip() for h in all_vals[0]]
    name_to_idx = {name: i + 1 for i, name in enumerate(header)}  # 1-based
    if key_col not in name_to_idx:
        raise RuntimeError(f"Key column {key_col} not found in header of {sheet_name}")

    # Map key -> sheet row index (1-based sheet rows; header is row 1)
    key_idx0 = name_to_idx[key_col] - 1
    key_to_row: Dict[str, int] = {}
    for r_i, row in enumerate(all_vals[1:], start=2):
        key = row[key_idx0] if key_idx0 < len(row) else ""
        key = str(key).strip()
        if key:
            key_to_row[key] = r_i

    # Decide which columns to update: ensure they exist
    col_indices = []
    for c in cols:
        if c not in name_to_idx:
            raise RuntimeError(
                f"Column {c} missing in {sheet_name}. Call ensure_header_has_columns(sh, sheet_name, cols) first."
            )
        col_indices.append(name_to_idx[c])

    # Optimize: update one contiguous range per row (best when cols are contiguous)
    start_col = min(col_indices)
    end_col = max(col_indices)
    start_letter = col_idx_to_letter(start_col)
    end_letter = col_idx_to_letter(end_col)

    # Build a consistent ordering for the range values:
    # we will fill the contiguous range; for columns not in `cols`, we preserve existing values by reading them once
    # Since `cols` should be contiguous tail, we can avoid per-row reads and just write full range values from updates,
    # but only if cols are exactly that contiguous range. Enforce this for simplicity.
    expected_contig = list(range(start_col, end_col + 1))
    # print("expected_contig", expected_contig)
    # print("sorted(col_indices)", col_indices)
    if sorted(col_indices) != expected_contig:
        raise RuntimeError(
            "cols are not contiguous in the sheet header. "
            "Make them contiguous (recommended: append summary cols at the end) or extend this function."
        )
    # Column names for the contiguous range
    range_cols = header[start_col - 1 : end_col]

    data_blocks: List[Dict[str, Any]] = []
    for upd in updates:
        key = str(upd.get(key_col, "")).strip()
        if not key:
            continue
        row_idx = key_to_row.get(key)
        if not row_idx:
            # key not found; skip quietly (v1) or raise if you prefer strictness
            continue

        row_vals = []
        for c in range_cols:
            v = upd.get(c, "")
            row_vals.append("" if v is None else str(v))

        rng = f"{sheet_name}!{start_letter}{row_idx}:{end_letter}{row_idx}"
        data_blocks.append({"range": rng, "values": [row_vals]})

    _values_batch_update(sh, data_blocks, chunk_size=chunk_size)



def read_cell_value(
    sh: gspread.Spreadsheet,
    sheet_name: str,
    a1: str,
    *,
    default: str = "",
    max_attempts: int = 6,
) -> str:
    """
    Read a single cell as a string with throttle backoff.
    Costs:
      - 1 call: ws.acell(a1)
    """
    ws = _get_or_create_ws(sh, sheet_name)
    for attempt in range(1, max_attempts + 1):
        try:
            v = ws.acell(a1).value
            if v is None:
                return default
            return str(v).strip()
        except Exception as e:
            if _is_throttle(e):
                _sleep_backoff(attempt)
                continue
            raise
    return default
