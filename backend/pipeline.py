"""End-to-end processing pipeline: raw -> mapped -> normalized -> matching."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi.concurrency import run_in_threadpool

from db import db
from ingestion import parse_file, store_raw_records
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
) -> Dict[str, int]:
    """Map -> normalize -> insert normalized -> lineage -> matching."""
    ingredient_index, product_map = await _load_reference()
    source_display = derive_source_name(source_file)

    normalized_docs: List[Dict[str, Any]] = []
    lineage_docs: List[Dict[str, Any]] = []
    for raw in raw_rows:
        try:
            mapped = map_record(raw, source_file)
            normalized, lineage = normalize_record(mapped, ingredient_index, product_map, source_display)
            normalized_docs.append(normalized)
            for l in lineage:
                l["recall_id"] = normalized["recall_id"]
                l["source_file"] = source_file
                l["created_at"] = datetime.now(timezone.utc).isoformat()
                lineage_docs.append(l)
        except Exception as e:  # noqa: BLE001 – never crash on bad row
            log.warning("bad row in %s: %s", source_file, e)
            continue

    if normalized_docs:
        await db.normalized_recalls.insert_many(normalized_docs, ordered=False)
    if lineage_docs:
        await db.data_lineage.insert_many(lineage_docs, ordered=False)

    alerts_created = 0
    if run_matching:
        for nd in normalized_docs:
            alerts_created += await run_matching_for_recall(db, nd)

    return {
        "normalized": len(normalized_docs),
        "lineage_rows": len(lineage_docs),
        "alerts_created": alerts_created,
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
            "lineage_rows": 0,
            "alerts_created": 0,
            "message": "file contained no valid data rows",
        }
    inserted_raw = await store_raw_records(db, rows, src)
    processed = await process_raw_rows(rows, src, run_matching=run_matching)
    return {
        "source_file": src,
        "raw_rows": inserted_raw,
        **processed,
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
