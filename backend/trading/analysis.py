"""News, sentiment, order-flow, large-transaction, panic & flash-event engines.

No fabricated data: if a source is unavailable it is reported UNAVAILABLE.
"""
import os
import time
import logging

import numpy as np
import httpx
import feedparser

logger = logging.getLogger("dacte.analysis")

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "").strip()
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://cryptopotato.com/feed/",
    "https://bitcoinmagazine.com/feed",
]

BULL_WORDS = ["surge", "rally", "soar", "bullish", "gain", "jump", "record high", "adoption",
              "approval", "inflow", "breakout", "upgrade", "partnership", "buy", "accumulate", "etf approval"]
BEAR_WORDS = ["crash", "plunge", "dump", "bearish", "loss", "hack", "exploit", "lawsuit", "ban",
              "outflow", "liquidation", "selloff", "fear", "decline", "fraud", "sec charges", "downgrade"]
CRITICAL_WORDS = ["hack", "exploit", "ban", "lawsuit", "sec", "fraud", "collapse", "bankrupt", "halt", "delist"]

ASSET_MAP = {"BTC": ["btc", "bitcoin"], "ETH": ["eth", "ethereum", "ether"],
             "SOL": ["sol", "solana"], "XRP": ["xrp", "ripple"]}


def _classify_headline(title: str):
    t = title.lower()
    bull = sum(1 for w in BULL_WORDS if w in t)
    bear = sum(1 for w in BEAR_WORDS if w in t)
    crit = any(w in t for w in CRITICAL_WORDS)
    if bull > bear:
        sent = "BULLISH"
    elif bear > bull:
        sent = "BEARISH"
    else:
        sent = "NEUTRAL"
    if crit:
        imp = "CRITICAL"
    elif bull + bear >= 2:
        imp = "HIGH"
    elif bull + bear == 1:
        imp = "MEDIUM"
    else:
        imp = "LOW"
    conf = min(100, 40 + (bull + bear) * 20)
    assets = [a for a, kw in ASSET_MAP.items() if any(k in t for k in kw)]
    return sent, imp, conf, assets


class NewsEngine:
    def __init__(self):
        self.items = []
        self.last_fetch = 0
        self.available = False
        self.source_status = {"newsapi": "UNAVAILABLE", "rss": "UNAVAILABLE"}

    async def refresh(self, force=False):
        if not force and time.time() - self.last_fetch < 180:
            return self.items
        items = []
        # NewsAPI.org
        if NEWSAPI_KEY:
            try:
                async with httpx.AsyncClient(timeout=12) as c:
                    r = await c.get("https://newsapi.org/v2/everything", params={
                        "q": "bitcoin OR ethereum OR crypto OR solana OR xrp",
                        "language": "en", "sortBy": "publishedAt", "pageSize": 30,
                        "apiKey": NEWSAPI_KEY})
                if r.status_code == 200 and r.json().get("status") == "ok":
                    for a in r.json().get("articles", []):
                        sent, imp, conf, assets = _classify_headline(a.get("title") or "")
                        items.append({
                            "source": (a.get("source") or {}).get("name") or "NewsAPI",
                            "headline": a.get("title"), "url": a.get("url"),
                            "timestamp": a.get("publishedAt"), "assets": assets or ["MARKET"],
                            "sentiment": sent, "importance": imp, "confidence": conf})
                    self.source_status["newsapi"] = "LIVE"
                else:
                    self.source_status["newsapi"] = "ERROR"
            except Exception as e:
                logger.warning("newsapi fetch failed: %s", e)
                self.source_status["newsapi"] = "ERROR"
        # RSS fallback / supplement
        rss_ok = False
        for url in RSS_FEEDS:
            try:
                d = feedparser.parse(url)
                for e in d.entries[:12]:
                    sent, imp, conf, assets = _classify_headline(e.get("title") or "")
                    items.append({
                        "source": d.feed.get("title", "RSS"),
                        "headline": e.get("title"), "url": e.get("link"),
                        "timestamp": e.get("published", ""), "assets": assets or ["MARKET"],
                        "sentiment": sent, "importance": imp, "confidence": conf})
                rss_ok = True
            except Exception as e:
                logger.warning("rss fetch failed %s: %s", url, e)
        self.source_status["rss"] = "LIVE" if rss_ok else "ERROR"
        # dedupe by headline
        seen, dedup = set(), []
        for it in items:
            key = (it.get("headline") or "")[:80]
            if key and key not in seen:
                seen.add(key)
                dedup.append(it)
        self.items = dedup[:60]
        self.available = len(self.items) > 0
        self.last_fetch = time.time()
        return self.items

    def score_for(self, asset: str):
        """News score -100..100 for an asset. None if unavailable."""
        if not self.available:
            return None, []
        rel = [i for i in self.items if asset in i["assets"] or "MARKET" in i["assets"]]
        rel = rel[:25]
        if not rel:
            return 0, []
        w = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1.2, "LOW": 0.5}
        num = 0.0
        den = 0.0
        for i in rel:
            wt = w.get(i["importance"], 1)
            s = 1 if i["sentiment"] == "BULLISH" else (-1 if i["sentiment"] == "BEARISH" else 0)
            num += s * wt * (i["confidence"] / 100)
            den += wt
        score = round(100 * num / den, 1) if den else 0
        top = sorted(rel, key=lambda x: w.get(x["importance"], 1), reverse=True)[:5]
        return score, top


def analyze_orderflow(orderbook, trades):
    """Order-book imbalance + trade aggressor flow -> score -100..100."""
    result = {"ob_imbalance": None, "buy_vol": 0, "sell_vol": 0, "spread_pct": None,
              "orderflow_score": 0, "available": False}
    if orderbook and orderbook.get("buy") and orderbook.get("sell"):
        bids = orderbook["buy"][:20]
        asks = orderbook["sell"][:20]
        bid_sz = sum(float(x["size"]) for x in bids)
        ask_sz = sum(float(x["size"]) for x in asks)
        tot = bid_sz + ask_sz
        imb = (bid_sz - ask_sz) / tot if tot else 0
        best_bid = float(bids[0]["price"])
        best_ask = float(asks[0]["price"])
        spread_pct = (best_ask - best_bid) / best_ask * 100 if best_ask else None
        result.update({"ob_imbalance": round(imb, 3), "spread_pct": round(spread_pct, 4) if spread_pct is not None else None})
        result["available"] = True
    buy_v = sell_v = 0.0
    if trades:
        for t in trades[:200]:
            sz = float(t["size"])
            # taker is the aggressor
            if t.get("buyer_role") == "taker":
                buy_v += sz
            elif t.get("seller_role") == "taker":
                sell_v += sz
        result["buy_vol"] = round(buy_v, 2)
        result["sell_vol"] = round(sell_v, 2)
        result["available"] = True
    flow = 0.0
    if result["ob_imbalance"] is not None:
        flow += result["ob_imbalance"] * 60
    tv = buy_v + sell_v
    if tv:
        flow += (buy_v - sell_v) / tv * 40
    result["orderflow_score"] = round(max(-100, min(100, flow)), 1)
    return result


def detect_large_transactions(trades):
    """Dynamic baseline per asset (relative to its own recent trade sizes)."""
    if not trades or len(trades) < 20:
        return {"classification": "NORMAL", "count": 0, "side": "UNKNOWN", "largest": 0, "events": []}
    sizes = np.array([float(t["size"]) for t in trades[:300]])
    mean = float(sizes.mean())
    std = float(sizes.std()) or 1e-9
    events = []
    for t in trades[:60]:
        sz = float(t["size"])
        z = (sz - mean) / std
        if z >= 3:
            if t.get("buyer_role") == "taker":
                side = "BUY"
            elif t.get("seller_role") == "taker":
                side = "SELL"
            else:
                side = "UNKNOWN"
            cls = "EXTREME" if z >= 6 else ("VERY_LARGE" if z >= 4.5 else "LARGE")
            events.append({"size": sz, "price": t.get("price"), "side": side, "z": round(z, 1), "class": cls})
    if not events:
        cls = "NORMAL"
    else:
        top = max(events, key=lambda e: e["z"])["class"]
        cls = top
    sides = [e["side"] for e in events if e["side"] != "UNKNOWN"]
    dominant = "UNKNOWN"
    if sides:
        dominant = max(set(sides), key=sides.count)
    return {"classification": cls, "count": len(events), "side": dominant,
            "largest": float(sizes.max()), "avg": round(mean, 2), "events": events[:8]}


def detect_panic(ta, orderflow, large_tx, trades):
    """Panic buy/sell scores from a combination of factors (never price alone)."""
    if not ta:
        return {"panic_sell": 0, "panic_buy": 0, "level": "NORMAL", "factors": []}
    factors = []
    sell = buy = 0.0
    pc = ta.get("price_change_pct", 0)
    vr = ta.get("volume_ratio", 1)
    atr_pct = (ta.get("atr") or 0) / ta["price"] * 100 if ta.get("price") else 0
    # volume spike
    if vr >= 2:
        w = min(30, vr * 8)
        factors.append(f"volume {vr}x avg")
        if pc < 0:
            sell += w
        else:
            buy += w
    # sharp move + volume
    if abs(pc) >= 1 and vr >= 1.5:
        if pc < 0:
            sell += min(25, abs(pc) * 8); factors.append(f"price {pc}% on volume")
        else:
            buy += min(25, abs(pc) * 8); factors.append(f"price +{pc}% on volume")
    # large tx pressure
    if large_tx and large_tx["classification"] in ("VERY_LARGE", "EXTREME"):
        if large_tx["side"] == "SELL":
            sell += 20; factors.append("large sell prints")
        elif large_tx["side"] == "BUY":
            buy += 20; factors.append("large buy prints")
        else:
            factors.append("large prints (side unknown)")
    # order-book imbalance / spread widening
    if orderflow and orderflow.get("ob_imbalance") is not None:
        if orderflow["ob_imbalance"] < -0.35:
            sell += 15; factors.append("bid thinning")
        elif orderflow["ob_imbalance"] > 0.35:
            buy += 15; factors.append("ask thinning")
    if orderflow and orderflow.get("spread_pct") and orderflow["spread_pct"] > 0.15:
        sell += 8; buy += 4; factors.append("spread widening")
    # volatility
    if atr_pct > 2:
        sell += 6; buy += 6; factors.append("elevated volatility")
    sell = min(100, sell)
    buy = min(100, buy)
    peak = max(sell, buy)
    if peak >= 80:
        level = "EXTREME"
    elif peak >= 60:
        level = "PANIC"
    elif peak >= 40:
        level = "STRONG"
    elif peak >= 20:
        level = "ELEVATED"
    else:
        level = "NORMAL"
    return {"panic_sell": round(sell, 1), "panic_buy": round(buy, 1), "level": level, "factors": factors}


def detect_flash(ta):
    """Flash crash / pump from rapid price change + volatility."""
    if not ta:
        return None
    pc = ta.get("price_change_pct", 0)
    vr = ta.get("volume_ratio", 1)
    if pc <= -2.5 and vr >= 2:
        return {"type": "FLASH_CRASH", "severity": min(100, int(abs(pc) * 15 + vr * 5)), "price_change_pct": pc}
    if pc >= 2.5 and vr >= 2:
        return {"type": "FLASH_PUMP", "severity": min(100, int(pc * 15 + vr * 5)), "price_change_pct": pc}
    return None


news_engine = NewsEngine()
