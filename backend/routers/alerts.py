from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from db import db

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    severity: str | None = None,
    matched_on: str | None = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    q: dict = {"user_id": user["user_id"]}
    if severity:
        q["severity"] = severity
    if matched_on:
        q["matched_on"] = matched_on
    items = await db.alerts.find(q, {"_id": 0}).sort("created_at", -1).limit(min(limit, 500)).to_list(500)
    unread = await db.alerts.count_documents({"user_id": user["user_id"], "read": False})
    return {"items": items, "total": len(items), "unread": unread}


@router.post("/{alert_id}/read")
async def mark_read(alert_id: str, user: dict = Depends(get_current_user)):
    await db.alerts.update_one({"alert_id": alert_id, "user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.alerts.update_many({"user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}
