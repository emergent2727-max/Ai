"""DACTE FastAPI server — autonomous trading bot control & telemetry API.

All routes are under /api. Secrets stay server-side; nothing sensitive is returned.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from trading.bot import bot
from trading.database import db, get_config, save_config, clean
from trading.config import DEFAULT_CONFIG

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("dacte.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await bot.startup()
    except Exception as e:
        logger.exception("bot startup failed: %s", e)
    yield
    await bot.shutdown()


app = FastAPI(title="DACTE — Delta Autonomous Crypto Trading Engine", lifespan=lifespan)
api = APIRouter(prefix="/api")


# ---------- models ----------
class ModeReq(BaseModel):
    mode: str


class LiveReq(BaseModel):
    enabled: bool
    confirm: str = ""


class ConfigReq(BaseModel):
    risk: dict | None = None
    weights: dict | None = None
    fees: dict | None = None
    timeframes: dict | None = None
    futures_symbols: list | None = None
    spot_symbols: list | None = None
    scan_interval_sec: int | None = None
    trailing_stop_enabled: bool | None = None
    use_llm_reasoning: bool | None = None


class ConfirmReq(BaseModel):
    confirm: str = ""


class ManualOrderReq(BaseModel):
    symbol: str
    side: str          # buy | sell
    size: int
    reduce_only: bool = False
    confirm: str = ""


class ProtectReq(BaseModel):
    symbol: str
    stop_pct: float = 1.0
    take_pct: float = 2.0


# ---------- telemetry ----------
@api.get("/")
async def root():
    return {"service": "DACTE", "status": "ok"}


@api.get("/bot/state")
async def bot_state():
    return bot.snapshot()


@api.get("/bot/config")
async def bot_config():
    cfg = dict(bot.cfg)
    cfg.pop("_id", None)
    return cfg


@api.put("/bot/config")
async def update_config(req: ConfigReq):
    cfg = bot.cfg
    data = req.model_dump(exclude_none=True)
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    await save_config(cfg)
    from trading import decision as dec
    bot.fee_engine = dec.FeeEngine(cfg["fees"])
    return {"ok": True, "config": {k: v for k, v in cfg.items() if k != "_id"}}


@api.post("/bot/mode")
async def set_mode(req: ModeReq):
    if req.mode not in ("off", "spot", "futures"):
        raise HTTPException(400, "invalid mode")
    return {"ok": True, "config": clean(await bot.set_mode(req.mode))}


@api.post("/bot/live")
async def set_live(req: LiveReq):
    if req.enabled and req.confirm.strip().upper() != "ENABLE REAL CAPITAL":
        raise HTTPException(400, "confirmation phrase required: 'ENABLE REAL CAPITAL'")
    return {"ok": True, "config": clean(await bot.set_live(req.enabled))}


@api.post("/bot/resume")
async def resume():
    res = await bot.resume()
    if not res.get("ok"):
        raise HTTPException(400, res.get("error"))
    return res


@api.post("/bot/stop")
async def stop():
    return await bot.stop("Manual kill switch")


@api.get("/account")
async def account():
    return {"account": bot.account, "unrealized_pnl": bot._unrealized_total(),
            "daily": bot.snapshot()["daily"]}


@api.get("/positions")
async def positions():
    out = []
    for p in bot.positions:
        if not p.get("size"):
            continue
        sym = bot.products_by_id.get(p.get("product_id"), {}).get("symbol", "?")
        entry = float(p.get("entry_price") or 0)
        mark = bot.mark_prices.get(sym, entry)
        cv = bot.products_by_id.get(p.get("product_id"), {}).get("contract_value", 1)
        upnl = (mark - entry) * float(p["size"]) * float(cv or 1) if entry else 0
        out.append({"symbol": sym, "size": p["size"], "side": "long" if p["size"] > 0 else "short",
                    "entry_price": entry, "mark_price": round(mark, 4),
                    "liquidation_price": p.get("liquidation_price"),
                    "margin": p.get("margin"), "unrealized_pnl": round(upnl, 4)})
    return out


@api.get("/orders")
async def orders():
    out = []
    for o in bot.open_orders:
        out.append({"id": o.get("id"), "symbol": o.get("product_symbol") or o.get("symbol"),
                    "side": o.get("side"), "size": o.get("size"),
                    "unfilled_size": o.get("unfilled_size"), "limit_price": o.get("limit_price"),
                    "order_type": o.get("stop_order_type") or o.get("order_type"),
                    "stop_price": o.get("stop_price"), "state": o.get("state")})
    return out


@api.get("/analysis")
async def analysis():
    return list(bot.analysis.values())


@api.get("/analysis/{symbol}")
async def analysis_one(symbol: str):
    snap = bot.analysis.get(symbol)
    if not snap:
        raise HTTPException(404, "no analysis yet for symbol")
    return snap


@api.get("/scanner")
async def scanner():
    return bot.market_scanner


@api.get("/events")
async def events(limit: int = 40):
    docs = await db.market_events.find().sort("ts", -1).limit(limit).to_list(limit)
    return [clean(d) for d in docs]


@api.get("/decisions")
async def decisions(limit: int = 40):
    docs = await db.bot_decisions.find().sort("ts", -1).limit(limit).to_list(limit)
    return [clean(d) for d in docs]


@api.get("/feed")
async def feed(limit: int = 60):
    docs = await db.decision_feed.find().sort("ts", -1).limit(limit).to_list(limit)
    return [clean(d) for d in docs]


@api.get("/news")
async def news(limit: int = 40):
    from trading.analysis import news_engine
    return {"available": news_engine.available, "sources": news_engine.source_status,
            "items": news_engine.items[:limit]}


@api.get("/connection")
async def connection():
    return bot.conn


# ---------- emergency ----------
@api.post("/emergency/cancel-orders")
async def emergency_cancel():
    return {"ok": True, "results": await bot.emergency_cancel_orders()}


@api.post("/emergency/close-positions")
async def emergency_close(req: ConfirmReq):
    if req.confirm.strip().upper() != "CLOSE ALL":
        raise HTTPException(400, "confirmation phrase required: 'CLOSE ALL'")
    return {"ok": True, "results": await bot.emergency_close_positions()}


@api.post("/positions/protect")
async def protect_position(req: ProtectReq):
    res = await bot.protect_position(req.symbol, req.stop_pct, req.take_pct)
    if not res.get("ok"):
        raise HTTPException(400, str(res.get("error")))
    return res


@api.get("/performance")
async def performance():
    decs = await db.bot_decisions.find().sort("ts", -1).limit(500).to_list(500)
    executed = [d for d in decs if d.get("result") == "EXECUTED"]
    no_trade = [d for d in decs if d.get("result") == "NO_TRADE"]
    failed = [d for d in decs if d.get("result") == "EXEC_FAILED"]
    by_symbol = {}
    for d in executed:
        by_symbol[d.get("symbol")] = by_symbol.get(d.get("symbol"), 0) + 1
    # realized pnl + fees from actual Delta fills (authoritative)
    fills = bot.recent_fills or []
    fees = 0.0
    realized = 0.0
    wins = losses = 0
    for f in fills:
        try:
            fees += float(f.get("commission") or 0)
        except (TypeError, ValueError):
            pass
        meta = f.get("meta_data") or {}
        pnl = meta.get("pnl")
        if pnl not in (None, ""):
            try:
                p = float(pnl)
                realized += p
                if p > 0:
                    wins += 1
                elif p < 0:
                    losses += 1
            except (TypeError, ValueError):
                pass
    closed = wins + losses
    return {
        "executed": len(executed), "no_trade": len(no_trade), "exec_failed": len(failed),
        "total_decisions": len(decs), "by_symbol": by_symbol,
        "avg_confidence_executed": round(sum(d.get("confidence", 0) for d in executed) / len(executed), 1) if executed else 0,
        "fills_count": len(fills), "total_fees": round(fees, 6),
        "realized_pnl_from_fills": round(realized, 6),
        "wins": wins, "losses": losses,
        "win_rate": round(wins / closed * 100, 1) if closed else None,
        "note": "Realized P&L/fees are from actual Delta fills. Win-rate covers closed round-trips only.",
    }


@api.post("/manual/order")
async def manual_order(req: ManualOrderReq):
    if req.confirm.strip().upper() != "CONFIRM":
        raise HTTPException(400, "confirmation phrase required: 'CONFIRM'")
    if bot.cfg["mode"] == "off":
        raise HTTPException(400, "TRADING OFF")
    if not bot.cfg["live_trading"]:
        raise HTTPException(400, "LIVE trading disabled")
    res = await bot.exec_engine.submit(bot.cfg, req.symbol, req.side, req.size,
                                       bot.cfg["mode"], reduce_only=req.reduce_only,
                                       meta={"manual": True})
    if not res.get("ok"):
        raise HTTPException(400, str(res.get("error")))
    return res


# ---------- backtesting (historical simulation only, never real orders) ----------
class BacktestReq(BaseModel):
    symbol: str = "BTCUSD"
    resolution: str = "15m"
    candles: int = 500
    fee: float = 0.0005


@api.post("/backtest")
async def backtest(req: BacktestReq):
    from trading.delta import client, DeltaError
    from trading import indicators as ind
    try:
        rows = await client.get_candles(req.symbol, req.resolution, req.candles)
    except DeltaError as e:
        raise HTTPException(400, str(e.payload))
    if not rows or len(rows) < 60:
        raise HTTPException(400, "not enough historical data")
    import numpy as np
    closes = np.array([float(r["close"]) for r in rows])
    ema_fast = ind._ema(closes, 9)
    ema_slow = ind._ema(closes, 21)
    equity = 1000.0
    pos = 0.0
    entry = 0.0
    trades = []
    wins = losses = 0
    fees_paid = 0.0
    for i in range(21, len(closes)):
        price = closes[i]
        if np.isnan(ema_fast[i]) or np.isnan(ema_slow[i]):
            continue
        cross_up = ema_fast[i] > ema_slow[i] and ema_fast[i - 1] <= ema_slow[i - 1]
        cross_dn = ema_fast[i] < ema_slow[i] and ema_fast[i - 1] >= ema_slow[i - 1]
        if cross_up and pos == 0:
            pos = equity / price
            entry = price
            fees_paid += equity * req.fee
            equity -= equity * req.fee
        elif cross_dn and pos > 0:
            gross = pos * price
            fee = gross * req.fee
            fees_paid += fee
            pnl = gross - fee - (pos * entry)
            equity = gross - fee
            trades.append(round(pnl, 2))
            wins += 1 if pnl > 0 else 0
            losses += 1 if pnl <= 0 else 0
            pos = 0.0
    if pos > 0:
        equity = pos * closes[-1]
    net_return = (equity - 1000.0) / 1000.0 * 100
    gross_wins = sum(t for t in trades if t > 0)
    gross_losses = -sum(t for t in trades if t < 0)
    pf = round(gross_wins / gross_losses, 2) if gross_losses else None
    return {
        "label": "HISTORICAL SIMULATION — not a guarantee of future results",
        "symbol": req.symbol, "resolution": req.resolution, "strategy": "EMA 9/21 crossover",
        "start_equity": 1000.0, "end_equity": round(equity, 2),
        "net_return_pct": round(net_return, 2), "num_trades": len(trades),
        "win_rate": round(wins / max(1, len(trades)) * 100, 1),
        "wins": wins, "losses": losses, "profit_factor": pf, "total_fees": round(fees_paid, 2),
    }


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
