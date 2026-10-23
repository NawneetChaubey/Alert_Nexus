"""Alerts router with user-scoped filtering, read tracking, and dismissal/archival."""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from db import db

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    severity: str | None = None,
    matched_on: str | None = None,
    status: str | None = None,
    include_dismissed: bool = False,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    q: dict = {"user_id": user["user_id"]}
    if severity:
        q["severity"] = severity
    if matched_on:
        q["matched_on"] = matched_on

    if status == "dismissed":
        q["dismissed"] = True
    elif status == "all" or include_dismissed:
        pass
    else:
        # Default: active alerts only (not dismissed)
        q["dismissed"] = {"$ne": True}

    items = await db.alerts.find(q, {"_id": 0}).sort("created_at", -1).limit(min(limit, 500)).to_list(500)
    unread = await db.alerts.count_documents({"user_id": user["user_id"], "read": False, "dismissed": {"$ne": True}})
    dismissed_count = await db.alerts.count_documents({"user_id": user["user_id"], "dismissed": True})
    return {
        "items": items,
        "total": len(items),
        "unread": unread,
        "dismissed_count": dismissed_count,
    }


@router.post("/{alert_id}/read")
async def mark_read(alert_id: str, user: dict = Depends(get_current_user)):
    res = await db.alerts.update_one(
        {"alert_id": alert_id, "user_id": user["user_id"]},
        {"$set": {"read": True}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True, "alert_id": alert_id, "read": True}


@router.post("/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.alerts.update_many(
        {"user_id": user["user_id"], "dismissed": {"$ne": True}},
        {"$set": {"read": True}},
    )
    return {"ok": True}


@router.post("/{alert_id}/dismiss")
@router.delete("/{alert_id}")
async def dismiss_alert(alert_id: str, user: dict = Depends(get_current_user)):
    """Dismiss/archive an alert for this user. Preserves compliance audit evidence."""
    res = await db.alerts.update_one(
        {"alert_id": alert_id, "user_id": user["user_id"]},
        {"$set": {"dismissed": True, "dismissed_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True, "alert_id": alert_id, "dismissed": True}


@router.post("/{alert_id}/restore")
async def restore_alert(alert_id: str, user: dict = Depends(get_current_user)):
    """Restore a previously dismissed alert."""
    res = await db.alerts.update_one(
        {"alert_id": alert_id, "user_id": user["user_id"]},
        {"$set": {"dismissed": False, "restored_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True, "alert_id": alert_id, "dismissed": False}
