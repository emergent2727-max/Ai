"""Telegram alert notifier (outbound only). Never blocks trading on failure."""
import os
import logging
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
logger = logging.getLogger("dacte.notify")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else None


def enabled() -> bool:
    return bool(TOKEN)


async def detect_chat_id():
    """Return the most recent chat id that has messaged the bot, else None."""
    if not API:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API}/getUpdates")
        data = r.json()
        if not data.get("ok"):
            return None
        for upd in reversed(data.get("result", [])):
            msg = upd.get("message") or upd.get("channel_post") or {}
            chat = msg.get("chat") or {}
            if chat.get("id"):
                return str(chat["id"])
    except Exception as e:
        logger.warning("detect_chat_id failed: %s", e)
    return None


async def send(chat_id: str, text: str):
    if not API or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{API}/sendMessage", json={
                "chat_id": chat_id, "text": text,
                "parse_mode": "HTML", "disable_web_page_preview": True})
        return r.status_code == 200 and r.json().get("ok")
    except Exception as e:
        logger.warning("telegram send failed: %s", e)
        return False
