"""Simple database-polling task queue.

Used for post-ingestion matching + (future) async AI explanations.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict

from db import db

log = logging.getLogger("queue")

_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}
_worker_task: asyncio.Task | None = None


def register_handler(job_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
    _handlers[job_type] = handler


async def enqueue(job_type: str, payload: Dict[str, Any]) -> str:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job = {
        "job_id": job_id,
        "job_type": job_type,
        "payload": payload,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.jobs.insert_one(dict(job))
    return job_id


async def _worker_loop() -> None:
    log.info("queue worker started (db polling mode)")
    while True:
        try:
            # Poll for a queued job and atomically set it to running
            job = await db.jobs.find_one_and_update(
                {"status": "queued"},
                {"$set": {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}},
                return_document=True,
            )
            
            if not job:
                # No jobs found, sleep and poll again
                await asyncio.sleep(5)
                continue
                
            handler = _handlers.get(job["job_type"])
            if not handler:
                log.warning("no handler for job_type=%s", job["job_type"])
                await db.jobs.update_one({"job_id": job["job_id"]}, {"$set": {"status": "failed", "error": "no_handler"}})
                continue
                
            try:
                await handler(job["payload"])
                await db.jobs.update_one({"job_id": job["job_id"]}, {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}})
            except Exception as e:  # noqa: BLE001
                log.exception("job failed")
                await db.jobs.update_one({"job_id": job["job_id"]}, {"$set": {"status": "failed", "error": str(e)}})
                
        except asyncio.CancelledError:
            log.info("queue worker shutting down")
            break
        except Exception as e:
            log.exception("Error in worker polling loop")
            await asyncio.sleep(5)


def start_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())


async def stop_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
