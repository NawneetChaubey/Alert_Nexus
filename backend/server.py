"""FastAPI server bootstrap for the Global Recall & Compliance Alert Platform."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).parent / ".env")

from db import db, ensure_indexes  # noqa: E402
from auth import router as auth_router  # noqa: E402
from pipeline import bootstrap_ingest, seed_reference_data  # noqa: E402
from queue_worker import start_worker, stop_worker  # noqa: E402
from routers.alerts import router as alerts_router  # noqa: E402
from routers.compliance import router as compliance_router  # noqa: E402
from routers.ingest import router as ingest_router  # noqa: E402
from routers.recalls import router as recalls_router  # noqa: E402
from routers.search import router as search_router  # noqa: E402
from routers.stats import router as stats_router  # noqa: E402
from routers.watchlist import router as watchlist_router  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("server")

app = FastAPI(title="Global Recall & Compliance Platform")

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health():
    return {"status": "ok"}


api_router.include_router(auth_router)
api_router.include_router(watchlist_router)
api_router.include_router(alerts_router)
api_router.include_router(recalls_router)
api_router.include_router(compliance_router)
api_router.include_router(stats_router)
api_router.include_router(ingest_router)
api_router.include_router(search_router)

app.include_router(api_router)

cors_origins_raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes()
    await seed_reference_data()
    start_worker()
    # Check configured DATA_DIR, Docker /app/data, or local project data folder
    configured_dir = os.environ.get("DATA_DIR")
    data_dir = Path(configured_dir) if configured_dir else Path("/app/data")
    if not data_dir.exists():
        local_data = Path(__file__).resolve().parent.parent / "data"
        if local_data.exists():
            data_dir = local_data

    if data_dir.exists():
        async def _bg_bootstrap():
            try:
                result = await bootstrap_ingest(data_dir)
                log.info("bootstrap ingest from %s: %s", data_dir, result)
            except Exception:
                log.exception("bootstrap ingest failed")

        asyncio.create_task(_bg_bootstrap())


@app.on_event("shutdown")
async def on_shutdown():
    await stop_worker()
