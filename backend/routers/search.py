from fastapi import APIRouter, Query

from db import db

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(q: str = Query(min_length=1), limit: int = 20):
    regex = {"$regex": q, "$options": "i"}
    recalls = await db.normalized_recalls.find(
        {"$or": [{"product_name": regex}, {"ingredients": regex}, {"recall_reason": regex}]},
        {"_id": 0, "recall_id": 1, "product_name": 1, "severity": 1, "region": 1, "source": 1},
    ).limit(limit).to_list(limit)
    ingredients = await db.ingredients.find({"name": regex}, {"_id": 0}).limit(limit).to_list(limit)
    banned = await db.banned_substances.find({"substance": regex}, {"_id": 0}).limit(limit).to_list(limit)
    return {"recalls": recalls, "ingredients": ingredients, "banned": banned}
