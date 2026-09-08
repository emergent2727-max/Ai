"""Execution, position-management & reconciliation engines.

Enforces the trading-mode gate (SPOT vs FUTURES) on the backend, idempotent
order submission via unique client_order_id, and never marks an order filled
until Delta confirms it.
"""
import uuid
import logging
from datetime import datetime, timezone

from .delta import client, DeltaError
from .database import db, log_audit, feed_push, log_event

logger = logging.getLogger("dacte.execution")


def gen_client_order_id() -> str:
    return ("dacte" + uuid.uuid4().hex)[:32]


def compute_stop_take(entry_price, direction, atr, structure, min_rr):
    """ATR + structure aware SL/TP. direction: 'long'|'short'."""
    atr = atr or entry_price * 0.005
    if direction == "long":
        stop = min(entry_price - 1.5 * atr, structure.get("support", entry_price) )
        stop = min(stop, entry_price - 0.5 * atr)
        risk = entry_price - stop
        take = entry_price + max(min_rr, 2.0) * risk
    else:
        stop = max(entry_price + 1.5 * atr, structure.get("resistance", entry_price))
        stop = max(stop, entry_price + 0.5 * atr)
        risk = stop - entry_price
        take = entry_price - max(min_rr, 2.0) * risk
    stop_dist_pct = abs(entry_price - stop) / entry_price * 100
    rr = abs(take - entry_price) / abs(entry_price - stop) if abs(entry_price - stop) else 0
    return round(stop, 4), round(take, 4), round(stop_dist_pct, 4), round(rr, 2)


class ExecutionEngine:
    def __init__(self, products_by_symbol):
        self.products = products_by_symbol  # symbol -> product dict

    def product_type(self, symbol):
        p = self.products.get(symbol)
        return p.get("contract_type") if p else None

    async def _already_submitted(self, coid):
        return await db.orders.find_one({"client_order_id": coid}) is not None

    async def submit(self, cfg, symbol, side, contracts, mode, reduce_only=False, meta=None):
        """Place a REAL order. Backend enforces the mode gate."""
        product = self.products.get(symbol)
        if not product:
            return {"ok": False, "error": f"unknown product {symbol}"}
        ctype = product.get("contract_type")
        # ---- MODE GATE (server-side, hard) ----
        if mode == "spot" and ctype != "spot":
            return {"ok": False, "error": "SPOT mode active — futures execution blocked"}
        if mode == "futures" and ctype not in ("perpetual_futures", "futures"):
            return {"ok": False, "error": "FUTURES mode active — spot execution blocked"}
        if mode == "off":
            return {"ok": False, "error": "TRADING OFF — execution blocked"}
        if not cfg.get("live_trading"):
            return {"ok": False, "error": "LIVE trading disabled — no real order sent"}

        coid = gen_client_order_id()
        order_doc = {
            "client_order_id": coid, "symbol": symbol, "product_id": product["id"],
            "side": side, "size": contracts, "mode": mode, "reduce_only": reduce_only,
            "state": "submitting", "created_at": datetime.now(timezone.utc).isoformat(),
            "meta": meta or {}, "delta_order_id": None,
        }
        await db.orders.insert_one(dict(order_doc))
        await feed_push(f"{mode.upper()} order submitting: {side} {contracts} {symbol}", "exec", symbol)
        try:
            res = await client.place_order(
                product_id=product["id"], size=contracts, side=side,
                order_type="market_order", reduce_only=reduce_only, client_order_id=coid)
            await db.orders.update_one({"client_order_id": coid}, {"$set": {
                "state": res.get("state", "acknowledged"), "delta_order_id": res.get("id"),
                "ack": res}})
            await feed_push(f"Order acknowledged id={res.get('id')} state={res.get('state')}", "exec", symbol)
            await log_audit("order_placed", {"coid": coid, "symbol": symbol, "side": side,
                                             "size": contracts, "delta_id": res.get("id")})
            return {"ok": True, "order": res, "client_order_id": coid}
        except DeltaError as e:
            await db.orders.update_one({"client_order_id": coid},
                                       {"$set": {"state": "rejected", "error": e.payload}})
            await feed_push(f"Order REJECTED {symbol}: {e.payload.get('error')}", "error", symbol)
            await log_audit("order_rejected", {"coid": coid, "error": e.payload})
            return {"ok": False, "error": e.payload}


class PositionManager:
    """Continuously re-evaluates each live position for HOLD/REDUCE/CLOSE/TP/TRAIL."""

    def evaluate(self, cfg, position, mark_price, ta, decision, panic):
        size = position.get("size", 0)
        if size == 0:
            return {"decision": "NONE", "reasons": []}
        entry = float(position.get("entry_price") or mark_price)
        long_pos = size > 0
        pnl_pct = ((mark_price - entry) / entry * 100) * (1 if long_pos else -1)
        meta = position.get("meta", {})
        stop = meta.get("stop")
        take = meta.get("take")
        trail = meta.get("trail")
        reasons = [f"uPnL {round(pnl_pct,2)}%"]
        act = "HOLD"

        if stop is not None:
            if long_pos and mark_price <= stop:
                return {"decision": "CLOSE", "reasons": reasons + ["stop hit"]}
            if (not long_pos) and mark_price >= stop:
                return {"decision": "CLOSE", "reasons": reasons + ["stop hit"]}
        if take is not None:
            if long_pos and mark_price >= take:
                return {"decision": "TAKE_PROFIT", "reasons": reasons + ["take-profit hit"]}
            if (not long_pos) and mark_price <= take:
                return {"decision": "TAKE_PROFIT", "reasons": reasons + ["take-profit hit"]}
        # reversal signal against the position
        if long_pos and decision["action"] in ("OPEN_SHORT", "SELL", "CLOSE_LONG") and decision["confidence"] > cfg["risk"]["min_confidence"]:
            return {"decision": "CLOSE", "reasons": reasons + ["reversal signal"]}
        if (not long_pos) and decision["action"] in ("OPEN_LONG", "BUY", "CLOSE_SHORT") and decision["confidence"] > cfg["risk"]["min_confidence"]:
            return {"decision": "CLOSE", "reasons": reasons + ["reversal signal"]}
        # panic against position
        if long_pos and panic["level"] in ("PANIC", "EXTREME") and panic["panic_sell"] > 60:
            return {"decision": "REDUCE", "reasons": reasons + ["panic selling"]}
        # trailing stop (volatility aware)
        if cfg.get("trailing_stop_enabled") and ta and ta.get("atr"):
            if pnl_pct > 1:
                act = "TRAIL"
                reasons.append("trailing stop active")
        return {"decision": act, "reasons": reasons}


async def reconcile(products_by_id):
    """REST reconciliation: authoritative account/position/order/fill state."""
    out = {"balances": None, "positions": [], "open_orders": [], "fills": [], "errors": []}
    try:
        out["balances"] = await client.get_balances()
    except DeltaError as e:
        out["errors"].append(("balances", e.payload))
    try:
        out["positions"] = await client.get_positions_margined() or []
    except DeltaError as e:
        out["errors"].append(("positions", e.payload))
    try:
        out["open_orders"] = await client.get_orders(states="open") or []
    except DeltaError as e:
        out["errors"].append(("orders", e.payload))
    try:
        out["fills"] = await client.get_fills(page_size=50) or []
    except DeltaError as e:
        out["errors"].append(("fills", e.payload))
    # persist snapshots
    if out["balances"] is not None:
        await db.account_snapshot.replace_one(
            {"_id": "latest"}, {"_id": "latest", "balances": out["balances"],
                                "ts": datetime.now(timezone.utc).isoformat()}, upsert=True)
    return out


def compute_equity(balances):
    """Sum available USD-equivalent equity from wallet balances."""
    if not balances:
        return {"equity": 0.0, "available": 0.0, "by_asset": []}
    equity = 0.0
    avail = 0.0
    by_asset = []
    for w in balances:
        bal = float(w.get("balance", 0) or 0)
        av = float(w.get("available_balance", 0) or 0)
        sym = w.get("asset_symbol", "?")
        by_asset.append({"asset": sym, "balance": round(bal, 8), "available": round(av, 8)})
        if sym in ("USD", "USDT", "USDC"):
            equity += bal
            avail += av
    return {"equity": round(equity, 4), "available": round(avail, 4), "by_asset": by_asset}
