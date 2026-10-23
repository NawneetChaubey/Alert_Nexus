"""Google OAuth2 Authentication."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from db import db

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "session_token"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


async def _get_session_token(request: Request) -> Optional[str]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        return token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(None, 1)[1].strip()
    return None


async def get_current_user(request: Request) -> dict:
    token = await _get_session_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_user_optional(request: Request) -> Optional[dict]:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


@router.post("/session")
async def create_session(request: Request, response: Response):
    """Exchange Google id_token for an app session cookie."""
    data = {}
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        pass
    
    token = data.get("id_token")
    if not token:
        raise HTTPException(status_code=400, detail="id_token required")

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="Google Client ID not configured on server")

    try:
        # Verify the token with Google
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = idinfo.get("email")
    name = idinfo.get("name") or email
    picture = idinfo.get("picture")
    
    if not email:
        raise HTTPException(status_code=401, detail="Token does not contain email")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture, "last_login": datetime.now(timezone.utc).isoformat()}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": datetime.now(timezone.utc).isoformat(),
        })
        # Initialize empty watchlist
        await db.watchlists.insert_one({
            "user_id": user_id,
            "products": [],
            "ingredients": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    # Generate our own session token
    session_token = f"session_{uuid.uuid4().hex}"
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=COOKIE_MAX_AGE)
    
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {
            "user_id": user_id,
            "session_token": session_token,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
        }},
        upsert=True,
    )
    
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )
    
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {"user": user_doc}


@router.post("/demo-session")
async def demo_session(response: Response):
    """Log in as demo user for local development, demo flows, and automated testing."""
    session_token = "test_session_harness"
    user_doc = await db.users.find_one({"user_id": "test-user-harness"}, {"_id": 0})
    if not user_doc:
        user_doc = {
            "user_id": "test-user-harness",
            "email": "test-user@med-alert.local",
            "name": "Demo User",
            "picture": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(dict(user_doc))

    expires_at = datetime.now(timezone.utc) + timedelta(days=365)
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {
            "user_id": "test-user-harness",
            "session_token": session_token,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
        }},
        upsert=True,
    )

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        max_age=COOKIE_MAX_AGE,
        httponly=False,
        secure=False,
        samesite="lax",
        path="/",
    )
    return {"user": user_doc, "session_token": session_token}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = await _get_session_token(request)
    if token and token != "test_session_harness":
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
