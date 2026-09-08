"""MongoDB access layer + collection helpers (async, motor)."""
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .config import DEFAULT_CONFIG

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = _client[os.environ["DB_NAME"]]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(doc: dict) -> dict:
    """Strip Mongo _id for JSON responses."""
    if doc and "_id" in doc:
        doc = {k: v for k, v in doc.items() if k != "_id"}
    return doc


async def get_config() -> dict:
    cfg = await db.bot_config.find_one({"_id": "bot_config"})
    if not cfg:
        cfg = dict(DEFAULT_CONFIG)
        await db.bot_config.insert_one(dict(cfg))
    # backfill any new default keys
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in cfg.items()})
    for k, v in DEFAULT_CONFIG.items():
        if isinstance(v, dict):
            m = dict(v)
            m.update(cfg.get(k, {}) or {})
            merged[k] = m
    return merged


async def save_config(cfg: dict) -> dict:
    cfg["_id"] = "bot_config"
    await db.bot_config.replace_one({"_id": "bot_config"}, cfg, upsert=True)
    return cfg


async def log_event(kind: str, severity: str, symbol: str, message: str, data: dict = None):
    doc = {
        "ts": now_iso(),
        "kind": kind,
        "severity": severity,
        "symbol": symbol,
        "message": message,
        "data": data or {},
    }
    await db.market_events.insert_one(dict(doc))
    return clean(doc)


async def log_decision(doc: dict):
    doc = dict(doc)
    doc["ts"] = now_iso()
    await db.bot_decisions.insert_one(dict(doc))
    return clean(doc)


async def log_audit(action: str, detail: dict):
    await db.audit_logs.insert_one({"ts": now_iso(), "action": action, "detail": detail})


async def feed_push(line: str, tag: str = "info", symbol: str = ""):
    doc = {"ts": now_iso(), "line": line, "tag": tag, "symbol": symbol}
    await db.decision_feed.insert_one(dict(doc))
    # keep collection bounded
    count = await db.decision_feed.estimated_document_count()
    if count > 1200:
        old = db.decision_feed.find().sort("ts", 1).limit(300)
        ids = [d["_id"] async for d in old]
        if ids:
            await db.decision_feed.delete_many({"_id": {"$in": ids}})
    return clean(doc)
