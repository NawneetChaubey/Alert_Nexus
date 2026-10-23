from fastapi import APIRouter

from db import db

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("")
async def list_compliance(region: str | None = None):
    q: dict = {}
    if region:
        q["region"] = region
    items = await db.banned_substances.find(q, {"_id": 0}).to_list(500)
    regions = await db.banned_substances.distinct("region")
    return {"items": items, "regions": sorted(regions)}
