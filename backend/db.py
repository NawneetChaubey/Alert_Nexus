import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

log = logging.getLogger("db")
load_dotenv(Path(__file__).parent / ".env")

_mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_db_name = os.environ.get("DB_NAME", "med_alert")
_use_mock_env = os.environ.get("USE_MOCK_MONGO", "").strip().lower()

_client = None

if _use_mock_env in ("true", "1", "yes"):
    from mongomock_motor import AsyncMongoMockClient
    _client = AsyncMongoMockClient()
    log.info("Using in-process AsyncMongoMockClient (USE_MOCK_MONGO=true)")
else:
    try:
        import pymongo
        # Probe MongoDB connection quickly with timeout
        test_conn = pymongo.MongoClient(_mongo_url, serverSelectionTimeoutMS=800)
        test_conn.server_info()
        from motor.motor_asyncio import AsyncIOMotorClient
        _client = AsyncIOMotorClient(_mongo_url)
        log.info("Connected to live MongoDB at %s", _mongo_url)
    except Exception as e:
        from mongomock_motor import AsyncMongoMockClient
        _client = AsyncMongoMockClient()
        log.info("Live MongoDB unavailable at %s (%s). Falling back to in-process AsyncMongoMockClient.", _mongo_url, e)

db = _client[_db_name]


async def ensure_indexes():
    """Create indexes used across collections."""
    await db.users.create_index("user_id", unique=True)
    await db.users.create_index("email", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("expires_at")

    await db.raw_recalls.create_index("source_file")
    await db.normalized_recalls.create_index("recall_id", unique=True)
    await db.normalized_recalls.create_index("product_name")
    await db.normalized_recalls.create_index("severity")
    await db.normalized_recalls.create_index("region")
    await db.normalized_recalls.create_index("category")
    await db.normalized_recalls.create_index("source")

    await db.alerts.create_index("user_id")
    await db.alerts.create_index([("user_id", 1), ("recall_id", 1)], unique=True)
    await db.alerts.create_index("created_at")

    await db.watchlists.create_index("user_id", unique=True)

    await db.ingredients.create_index("name", unique=True)
    await db.product_ingredient_map.create_index("product_name", unique=True)
    await db.banned_substances.create_index([("region", 1), ("substance", 1)], unique=True)

    await db.data_lineage.create_index("recall_id")
    await db.jobs.create_index("created_at")
