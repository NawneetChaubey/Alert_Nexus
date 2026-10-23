from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user
from db import db
from llm_service import explain_recall

router = APIRouter(prefix="/recalls", tags=["recalls"])


@router.get("")
async def list_recalls(
    q: str | None = None,
    severity: str | None = None,
    region: str | None = None,
    category: str | None = None,
    source: str | None = None,
    sort_by: str = "newest",
    limit: int = 50,
    skip: int = 0,
):
    query: dict = {}
    if severity:
        query["severity"] = severity
    if region:
        query["region"] = region
    if category:
        query["category"] = category
    if source:
        query["source"] = source
    if q:
        query["$or"] = [
            {"product_name": {"$regex": q, "$options": "i"}},
            {"recall_reason": {"$regex": q, "$options": "i"}},
            {"ingredients": {"$regex": q, "$options": "i"}},
        ]
    total = await db.normalized_recalls.count_documents(query)

    # Deterministic compound sorting
    if sort_by == "oldest":
        sort_order = [("timestamp", 1), ("recall_id", 1)]
    else:
        sort_order = [("timestamp", -1), ("recall_id", -1)]

    items = await (
        db.normalized_recalls.find(query, {"_id": 0})
        .sort(sort_order)
        .skip(skip)
        .limit(min(limit, 200))
        .to_list(200)
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/history")
async def recall_history(limit: int = 50):
    items = await db.normalized_recalls.find({}, {"_id": 0}).sort("timestamp", -1).limit(min(limit, 200)).to_list(200)
    return {"items": items, "total": len(items)}


@router.get("/{recall_id}")
async def get_recall(recall_id: str):
    rec = await db.normalized_recalls.find_one({"recall_id": recall_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="recall not found")
    lineage = await db.data_lineage.find({"recall_id": recall_id}, {"_id": 0}).to_list(200)
    return {"recall": rec, "lineage": lineage}


@router.post("/{recall_id}/explain")
async def explain(recall_id: str, user: dict = Depends(get_current_user)):
    rec = await db.normalized_recalls.find_one({"recall_id": recall_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="recall not found")
    cached = await db.recall_explanations.find_one({"recall_id": recall_id}, {"_id": 0})
    if cached:
        return cached
    explanation = await explain_recall(rec)
    doc = {"recall_id": recall_id, "explanation": explanation, "model": "claude-sonnet-4-5"}
    await db.recall_explanations.insert_one(dict(doc))
    return doc
