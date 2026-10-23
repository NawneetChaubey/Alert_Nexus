from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from db import db
from matching import run_matching_for_user

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    value: str = Field(min_length=1, max_length=120)


async def _get_wl(user_id: str) -> dict:
    wl = await db.watchlists.find_one({"user_id": user_id}, {"_id": 0})
    if not wl:
        wl = {"user_id": user_id, "products": [], "ingredients": [], "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.watchlists.insert_one(dict(wl))
    return wl


@router.get("")
async def get_watchlist(user: dict = Depends(get_current_user)):
    return await _get_wl(user["user_id"])


@router.post("/products")
async def add_product(item: WatchlistItem, user: dict = Depends(get_current_user)):
    await db.watchlists.update_one(
        {"user_id": user["user_id"]},
        {"$addToSet": {"products": item.value.strip()}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    wl = await _get_wl(user["user_id"])
    created = await run_matching_for_user(db, user["user_id"], wl)
    return {"watchlist": wl, "alerts_created": created}


@router.delete("/products/{value}")
async def remove_product(value: str, user: dict = Depends(get_current_user)):
    await db.watchlists.update_one(
        {"user_id": user["user_id"]},
        {"$pull": {"products": value}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return await _get_wl(user["user_id"])


@router.post("/ingredients")
async def add_ingredient(item: WatchlistItem, user: dict = Depends(get_current_user)):
    await db.watchlists.update_one(
        {"user_id": user["user_id"]},
        {"$addToSet": {"ingredients": item.value.strip().lower()}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    wl = await _get_wl(user["user_id"])
    created = await run_matching_for_user(db, user["user_id"], wl)
    return {"watchlist": wl, "alerts_created": created}


@router.delete("/ingredients/{value}")
async def remove_ingredient(value: str, user: dict = Depends(get_current_user)):
    await db.watchlists.update_one(
        {"user_id": user["user_id"]},
        {"$pull": {"ingredients": value.lower()}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return await _get_wl(user["user_id"])


@router.get("/suggestions")
async def suggestions():
    """Suggest known ingredients (autocomplete helper)."""
    ings = await db.ingredients.find({}, {"_id": 0, "name": 1, "category": 1}).to_list(500)
    return {"ingredients": [i["name"] for i in ings]}
