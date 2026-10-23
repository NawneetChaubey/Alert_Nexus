"""Raw ingestion layer. Parses CSV + Excel files into raw rows + stores them as-is."""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd

log = logging.getLogger("ingestion")


def parse_csv_bytes(data: bytes) -> List[Dict[str, Any]]:
    """Parse CSV bytes robustly (tolerates bad lines)."""
    text = data.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []
    for r in reader:
        rows.append({k: v for k, v in r.items() if v is not None})
    return rows


def _df_to_clean_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    df = df.where(pd.notnull(df), None)
    clean: List[Dict[str, Any]] = []
    for r in df.to_dict("records"):
        row: Dict[str, Any] = {}
        for k, v in r.items():
            if v is None:
                continue
            sv = str(v).strip()
            if not sv or sv.lower() == "nan":
                continue
            row[str(k)] = sv
        if row:
            clean.append(row)
    return clean


def parse_excel_bytes(data: bytes, header_row: int | None = None) -> List[Dict[str, Any]]:
    """Auto-detect header row.

    Some workbooks (EU Safety Gate) have a banner at row 0 with real headers on row 1.
    Most workbooks have headers at row 0. Strategy: try row 0; if most columns look
    like 'Unnamed: N' (pandas placeholder), retry with row 1.
    """
    if header_row is not None:
        return _df_to_clean_rows(pd.read_excel(io.BytesIO(data), header=header_row))

    df0 = pd.read_excel(io.BytesIO(data), header=0)
    cols = [str(c) for c in df0.columns]
    unnamed = sum(1 for c in cols if c.startswith("Unnamed:"))
    if cols and unnamed / len(cols) >= 0.5 and len(df0) > 0:
        new_cols = [str(x).strip() for x in df0.iloc[0]]
        df1 = df0.iloc[1:].copy()
        df1.columns = new_cols
        return _df_to_clean_rows(df1)
    return _df_to_clean_rows(df0)


def parse_file(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    data = path.read_bytes()
    if len(data) == 0:
        raise ValueError("File is empty (0 bytes)")
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        try:
            return parse_excel_bytes(data)
        except Exception as e:
            raise ValueError(f"Corrupted or invalid Excel file: {e}") from e
    if suffix == ".csv":
        try:
            return parse_csv_bytes(data)
        except Exception as e:
            log.warning("csv parse fallback for %s: %s", path.name, e)
            try:
                df = pd.read_csv(io.BytesIO(data), on_bad_lines="skip", low_memory=False)
                df = df.where(pd.notnull(df), None)
                return _df_to_clean_rows(df)
            except Exception as e2:
                raise ValueError(f"Corrupted or invalid CSV file: {e2}") from e2
    raise ValueError(f"Unsupported file type: {suffix}")


async def store_raw_records(db, rows: Iterable[Dict[str, Any]], source_file: str) -> int:
    """Store rows as-is with provenance. Returns count inserted."""
    batch: List[Dict[str, Any]] = []
    for r in rows:
        # Mongo requires string keys; drop None keys and cast everything to str
        clean = {str(k): v for k, v in r.items() if k is not None and str(k).strip() != ""}
        batch.append({
            "raw_id": f"raw_{source_file}_{len(batch)}_{datetime.now(timezone.utc).timestamp()}",
            "source_file": source_file,
            "raw_payload": clean,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
    if not batch:
        return 0
    await db.raw_recalls.insert_many(batch, ordered=False)
    return len(batch)
