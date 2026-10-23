from fastapi import APIRouter

from db import db

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/ingestion")
async def ingestion_stats():
    total_raw = await db.raw_recalls.count_documents({})
    total_normalized = await db.normalized_recalls.count_documents({})

    pipeline_sev = [{"$group": {"_id": "$severity", "count": {"$sum": 1}}}]
    sev_dist = {d["_id"]: d["count"] async for d in db.normalized_recalls.aggregate(pipeline_sev)}

    pipeline_reg = [{"$group": {"_id": "$region", "count": {"$sum": 1}}}]
    region_dist = {d["_id"]: d["count"] async for d in db.normalized_recalls.aggregate(pipeline_reg)}

    pipeline_src = [{"$group": {"_id": "$source", "count": {"$sum": 1}}}]
    source_dist = {d["_id"]: d["count"] async for d in db.normalized_recalls.aggregate(pipeline_src)}

    pipeline_cat = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
    cat_dist = {d["_id"]: d["count"] async for d in db.normalized_recalls.aggregate(pipeline_cat)}

    # Confidence buckets
    buckets = {"0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    async for r in db.normalized_recalls.find({}, {"_id": 0, "confidence_score": 1}):
        c = r.get("confidence_score", 0) or 0
        if c <= 0.2:
            buckets["0-0.2"] += 1
        elif c <= 0.4:
            buckets["0.2-0.4"] += 1
        elif c <= 0.6:
            buckets["0.4-0.6"] += 1
        elif c <= 0.8:
            buckets["0.6-0.8"] += 1
        else:
            buckets["0.8-1.0"] += 1

    # Inference rate per field
    inferred_counts: dict[str, int] = {}
    async for r in db.normalized_recalls.find({}, {"_id": 0, "inferred_fields": 1}):
        for f in r.get("inferred_fields") or []:
            inferred_counts[f] = inferred_counts.get(f, 0) + 1

    return {
        "total_raw": total_raw,
        "total_normalized": total_normalized,
        "severity": sev_dist,
        "region": region_dist,
        "source": source_dist,
        "category": cat_dist,
        "confidence_buckets": buckets,
        "inferred_field_counts": inferred_counts,
    }
