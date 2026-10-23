"""End-to-end processing pipeline: raw -> mapped -> normalized -> matching."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi.concurrency import run_in_threadpool

from db import db
from ingestion import manual_upload_archive_dir, parse_file, store_raw_records
from mapping import map_record, derive_source_name
from matching import run_matching_for_recall
from normalization import normalize_record
from seed_data import BANNED_SUBSTANCES, INGREDIENT_MASTER, PRODUCT_INGREDIENT_MAP

log = logging.getLogger("pipeline")


async def seed_reference_data() -> None:
    """Load seed data on first boot."""
    if await db.ingredients.count_documents({}) == 0:
        await db.ingredients.insert_many([dict(i) for i in INGREDIENT_MASTER])
    if await db.product_ingredient_map.count_documents({}) == 0:
        await db.product_ingredient_map.insert_many([
            {"product_name": p["product_name"], "ingredients": list(p["ingredients"])}
            for p in PRODUCT_INGREDIENT_MAP
        ])
    if await db.banned_substances.count_documents({}) == 0:
        await db.banned_substances.insert_many([dict(b) for b in BANNED_SUBSTANCES])

    # Ensure demo/harness user and session exist
    if await db.users.count_documents({"user_id": "test-user-harness"}) == 0:
        await db.users.insert_one({
            "user_id": "test-user-harness",
            "email": "test-user@med-alert.local",
            "name": "Demo User",
            "picture": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    if await db.user_sessions.count_documents({"session_token": "test_session_harness"}) == 0:
        await db.user_sessions.insert_one({
            "session_token": "test_session_harness",
            "user_id": "test-user-harness",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    if await db.watchlists.count_documents({"user_id": "test-user-harness"}) == 0:
        await db.watchlists.insert_one({
            "user_id": "test-user-harness",
            "products": ["Skin Lightening"],
            "ingredients": ["hydroquinone", "mercury"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })


async def _load_reference() -> tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    ingredient_index = await db.ingredients.find({}, {"_id": 0}).to_list(1000)
    product_rows = await db.product_ingredient_map.find({}, {"_id": 0}).to_list(2000)
    product_map = {p["product_name"].lower(): list(p.get("ingredients") or []) for p in product_rows}
    return ingredient_index, product_map


async def process_raw_rows(
    raw_rows: List[Dict[str, Any]],
    source_file: str,
    run_matching: bool = True,
) -> Dict[str, Any]:
    """Map -> normalize -> insert normalized -> lineage -> matching with detailed failure tracking."""
    ingredient_index, product_map = await _load_reference()
    source_display = derive_source_name(source_file)

    normalized_docs: List[Dict[str, Any]] = []
    lineage_docs: List[Dict[str, Any]] = []
    failed_rows = 0
    row_errors: List[Dict[str, Any]] = []

    for idx, raw in enumerate(raw_rows):
        row_num = idx + 1
        # Detect empty or blank rows
        if not raw or not any(str(v).strip() and str(v).strip().lower() != "nan" for v in raw.values() if v is not None):
            failed_rows += 1
            row_errors.append({"row": row_num, "error": "Row is completely empty or blank"})
            continue

        try:
            mapped = map_record(raw, source_file)
            normalized, lineage = normalize_record(mapped, ingredient_index, product_map, source_display)
            normalized_docs.append(normalized)
            for l in lineage:
                l["recall_id"] = normalized["recall_id"]
                l["source_file"] = source_file
                l["created_at"] = datetime.now(timezone.utc).isoformat()
                lineage_docs.append(l)
        except Exception as e:
            failed_rows += 1
            row_errors.append({"row": row_num, "error": str(e)})
            log.warning("Row %d rejected in %s: %s", row_num, source_file, e)
            continue

    if normalized_docs:
        try:
            await db.normalized_recalls.insert_many(normalized_docs, ordered=False)
        except Exception as e:
            # On re-ingestion, duplicate key errors are safely ignored
            log.info("Batch normalized insert completed (duplicate keys ignored): %s", e)
    if lineage_docs:
        try:
            await db.data_lineage.insert_many(lineage_docs, ordered=False)
        except Exception as e:
            log.info("Batch lineage insert completed: %s", e)

    alerts_created = 0
    if run_matching:
        for nd in normalized_docs:
            try:
                alerts_created += await run_matching_for_recall(db, nd)
            except Exception as e:
                log.error("Matching error for recall %s: %s", nd.get("recall_id"), e)

    # Calculate status contract
    if len(normalized_docs) == 0 and len(raw_rows) > 0:
        status = "failed"
    elif failed_rows > 0:
        status = "partial_success"
    else:
        status = "success"

    return {
        "source_file": source_file,
        "raw_rows": len(raw_rows),
        "normalized": len(normalized_docs),
        "failed_rows": failed_rows,
        "lineage_rows": len(lineage_docs),
        "alerts_created": alerts_created,
        "status": status,
        "errors": row_errors[:50],
    }


async def ingest_file(path: Path, run_matching: bool = True, source_name: str | None = None) -> Dict[str, Any]:
    """Full pipeline for a single file path."""
    src = source_name or path.name
    rows = await run_in_threadpool(parse_file, path)
    if not rows:
        return {
            "source_file": src,
            "raw_rows": 0,
            "normalized": 0,
            "failed_rows": 0,
            "lineage_rows": 0,
            "alerts_created": 0,
            "status": "failed",
            "errors": [{"row": 0, "error": "File contained no valid data rows"}],
            "message": "file contained no valid data rows",
        }
    inserted_raw = await store_raw_records(db, rows, src)
    processed = await process_raw_rows(rows, src, run_matching=run_matching)
    return {
        **processed,
        "raw_rows": inserted_raw,
        "source_file": src,
    }


async def bootstrap_ingest(data_dir: Path) -> Dict[str, Any]:
    """Per-file idempotent ingest: skip files already present in raw_recalls.source_file."""
    already_ingested = set(await db.raw_recalls.distinct("source_file"))
    results: List[Dict[str, Any]] = []
    for p in sorted(data_dir.iterdir()):
        if p.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            continue
        # Skip redundant 14k-row bulk archive to keep bootstrap snappy (< 3 seconds)
        if "regional" in p.name.lower():
            continue
        if p.name in already_ingested:
            results.append({"source_file": p.name, "skipped": True})
            continue
        try:
            r = await ingest_file(p, run_matching=False)
            results.append(r)
        except Exception as e:  # noqa: BLE001
            log.exception("bootstrap ingest failed for %s", p.name)
            results.append({"source_file": p.name, "error": str(e)})

    # Backfill matches for any pre-seeded watchlists
    watchlists = await db.watchlists.find({}, {"_id": 0}).to_list(100)
    for wl in watchlists:
        try:
            from matching import run_matching_for_user
            await run_matching_for_user(db, wl["user_id"], wl)
        except Exception:
            pass

    return {"results": results}


async def restore_manual_uploads() -> Dict[str, Any]:
    """Reload archived portal uploads into a fresh in-memory database on startup."""
    archive_dir = manual_upload_archive_dir()
    if not archive_dir.exists():
        return {"restored": 0, "results": []}

    results: List[Dict[str, Any]] = []
    for manifest_path in sorted(archive_dir.glob("*.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            stored_name = str(manifest.get("stored_file") or "")
            if not stored_name or Path(stored_name).name != stored_name:
                raise ValueError("invalid archived filename")

            archived_path = archive_dir / stored_name
            if not archived_path.is_file():
                raise FileNotFoundError(f"Archived upload is missing: {stored_name}")

            result = await ingest_file(
                archived_path,
                run_matching=True,
                source_name=str(manifest.get("source_file") or stored_name),
            )
            results.append(result)
        except Exception as exc:  # noqa: BLE001
            log.exception("failed to restore archived upload %s", manifest_path.name)
            results.append({"source_file": manifest_path.name, "error": str(exc)})

    restored = sum(1 for item in results if item.get("raw_rows", 0) > 0)
    return {"restored": restored, "results": results}
