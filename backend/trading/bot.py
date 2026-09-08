"""Autonomous bot orchestrator: state machine, analysis loop, execution gate,
connection health, reconciliation, public/private WebSockets, safety controls.
"""
import asyncio
import json
import time
import logging
import hmac
import hashlib
import os
from collections import deque
from datetime import datetime, timezone

import websockets

from .config import DEFAULT_CONFIG
from .delta import client, DeltaError, SECRET, KEY
from . import indicators as ind
from . import analysis as an
from .analysis import news_engine
from . import decision as dec
from . import notify as notify_mod
from .execution import (ExecutionEngine, PositionManager, reconcile, compute_equity,
                        compute_stop_take, gen_client_order_id)
from .database import (db, get_config, save_config, log_event, log_decision,
                       log_audit, feed_push, now_iso)

logger = logging.getLogger("dacte.bot")

WS_PUBLIC = os.environ["DELTA_WS_PUBLIC"]
WS_PRIVATE = os.environ["DELTA_WS_PRIVATE"]


class Bot:
    def __init__(self):
        self.cfg = dict(DEFAULT_CONFIG)
        self.status = "PAUSED"          # ACTIVE | PAUSED | ERROR
        self.state = "PAUSED"           # ANALYZING | WAITING | SIGNAL | EXECUTING | MANAGING | PAUSED
        self.products_by_symbol = {}
        self.products_by_id = {}
        self.exec_engine = None
        self.pos_manager = PositionManager()
        self.fee_engine = None
        self.sizer = dec.PositionSizer()
        self.risk_engine = dec.RiskEngine()
        self.decision_engine = dec.DecisionEngine()

        self.analysis = {}              # symbol -> latest analysis snapshot
        self.account = {"equity": 0.0, "available": 0.0, "by_asset": []}
        self.positions = []
        self.open_orders = []
        self.recent_fills = []
        self.market_scanner = []

        self.conn = {"rest": "INIT", "ws_public": "INIT", "ws_private": "INIT",
                     "market_data": "INIT", "news": "INIT", "account": "INIT",
                     "time_synced": True, "required_ip": None, "server_time_drift": 0.0}

        self.mark_prices = {}           # symbol -> live price (WS or REST)
        self.last_md_ts = 0

        self.daily = {"date": self._today(), "trades": 0, "realized_pnl": 0.0,
                      "consecutive_losses": 0, "trades_this_hour": deque(maxlen=200)}
        self.cooldowns = {}             # symbol -> ts until
        self.last_trade_ts = 0
        self.paused_reason = None

        self._tasks = []
        self._running = False

    def _today(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _roll_daily(self):
        if self.daily["date"] != self._today():
            self.daily = {"date": self._today(), "trades": 0, "realized_pnl": 0.0,
                          "consecutive_losses": 0, "trades_this_hour": deque(maxlen=200)}

    # -------- lifecycle --------
    async def startup(self):
        self.cfg = await get_config()
        self.fee_engine = dec.FeeEngine(self.cfg["fees"])
        await self._load_products()
        self._running = True
        # RESTART RECOVERY: always start PAUSED, reconcile first
        self.status = "PAUSED"
        self.state = "PAUSED"
        self.paused_reason = "Restarted — autonomous trading paused pending reconciliation & user activation"
        await log_audit("startup", {"mode": self.cfg["mode"], "live": self.cfg["live_trading"]})
        await feed_push("System started — TRADING PAUSED (restart recovery)", "system")
        self._tasks = [
            asyncio.create_task(self._scan_loop()),
            asyncio.create_task(self._reconcile_loop()),
            asyncio.create_task(self._public_ws_loop()),
            asyncio.create_task(self._private_ws_loop()),
            asyncio.create_task(self._news_loop()),
            asyncio.create_task(self._telegram_loop()),
        ]

    async def notify(self, text):
        if not self.cfg.get("alerts_enabled"):
            return
        cid = self.cfg.get("telegram_chat_id")
        if cid:
            await notify_mod.send(cid, text)

    async def _telegram_loop(self):
        """Auto-detect chat id once the user messages the bot; then idle-poll."""
        greeted = bool(self.cfg.get("telegram_chat_id"))
        while self._running:
            try:
                if notify_mod.enabled() and not self.cfg.get("telegram_chat_id"):
                    cid = await notify_mod.detect_chat_id()
                    if cid:
                        self.cfg["telegram_chat_id"] = cid
                        await save_config(self.cfg)
                        await notify_mod.send(cid,
                            "✅ <b>DACTE alerts linked.</b>\nYou'll get a ping on every open, "
                            "protect, reduce, close, pause and resume.")
                        greeted = True
            except Exception as e:
                logger.warning("telegram loop: %s", e)
            await asyncio.sleep(20 if not greeted else 90)

    async def shutdown(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        await client.close()

    async def _load_products(self):
        try:
            futs = await client.get_products(contract_types="perpetual_futures")
            spots = await client.get_products(contract_types="spot")
            self.conn["rest"] = "CONNECTED"
            for p in (futs or []) + (spots or []):
                self.products_by_symbol[p["symbol"]] = p
                self.products_by_id[p["id"]] = p
            self.exec_engine = ExecutionEngine(self.products_by_symbol)
            await self._build_scanner(futs or [])
        except DeltaError as e:
            self.conn["rest"] = "ERROR"
            self.conn["required_ip"] = client.required_ip
            logger.error("product load failed: %s", e.payload)

    async def _build_scanner(self, futs):
        """Rank liquid perpetuals by 24h volume for display; filter quality."""
        try:
            tickers = await client.get_tickers(contract_types="perpetual_futures")
        except DeltaError:
            tickers = []
        rows = []
        for t in tickers or []:
            try:
                vol = float(t.get("volume") or 0)
                rows.append({"symbol": t.get("symbol"), "volume": vol,
                             "mark_price": float(t.get("mark_price") or 0),
                             "turnover_usd": float(t.get("turnover_usd") or 0)})
            except Exception:
                continue
        rows.sort(key=lambda r: r["turnover_usd"], reverse=True)
        self.market_scanner = rows[:20]

    # -------- market data --------
    async def _candles(self, symbol, resolution, count=200):
        key = f"{symbol}:{resolution}"
        cache = getattr(self, "_ccache", None)
        if cache is None:
            self._ccache = {}
            cache = self._ccache
        entry = cache.get(key)
        if entry and time.time() - entry[0] < 55:
            return entry[1]
        rows = await client.get_candles(symbol, resolution, count)
        cache[key] = (time.time(), rows)
        return rows

    # -------- analysis for one symbol --------
    async def analyze_symbol(self, symbol, mode, btc_trend_ta):
        tf = self.cfg["timeframes"]
        try:
            c_trend = await self._candles(symbol, tf["trend"])
            c_setup = await self._candles(symbol, tf["setup"])
            c_entry = await self._candles(symbol, tf["entry"])
            ob = await client.get_orderbook(symbol)
            trades = await client.get_trades(symbol)
            self.conn["market_data"] = "LIVE"
            self.last_md_ts = time.time()
        except DeltaError as e:
            self.conn["market_data"] = "STALE"
            return None

        ta_trend = ind.compute_ta(c_trend)
        ta_setup = ind.compute_ta(c_setup)
        ta_entry = ind.compute_ta(c_entry)
        if not ta_entry:
            return None
        structure = ind.compute_structure(c_setup or c_entry)
        regime = ind.compute_regime(ta_setup or ta_entry, structure)
        align, direction = ind.multi_timeframe_alignment(ta_trend, ta_setup, ta_entry)
        orderflow = an.analyze_orderflow(ob, trades)
        large_tx = an.detect_large_transactions(trades)
        panic = an.detect_panic(ta_entry, orderflow, large_tx, trades)
        flash = an.detect_flash(ta_entry)

        asset = symbol.replace("USD", "").replace("_INR", "")
        news_score, top_news = news_engine.score_for(asset)
        sentiment, sources = dec.sentiment_score(news_score, btc_trend_ta, orderflow)

        self.mark_prices[symbol] = ta_entry["price"]

        ta_multi = {"trend": ta_trend, "setup": ta_setup, "entry": ta_entry,
                    "alignment_score": align, "direction": direction}
        position = next((p for p in self.positions
                         if self.products_by_id.get(p.get("product_id"), {}).get("symbol") == symbol), None)

        decision = self.decision_engine.decide(
            self.cfg, symbol, mode, ta_multi, structure, regime, orderflow,
            sentiment, news_score, panic, large_tx, position)

        snap = {
            "symbol": symbol, "ts": now_iso(), "price": ta_entry["price"], "regime": regime,
            "ta": {"trend": ta_trend, "setup": ta_setup, "entry": ta_entry},
            "alignment": align, "direction": direction, "structure": structure,
            "orderflow": orderflow, "large_tx": large_tx, "panic": panic, "flash": flash,
            "sentiment": sentiment, "sentiment_sources": sources,
            "news_score": news_score, "top_news": top_news, "decision": decision,
        }
        self.analysis[symbol] = snap

        # emit events
        if flash:
            await log_event(flash["type"], "CRITICAL", symbol,
                            f"{flash['type']} severity {flash['severity']} ({flash['price_change_pct']}%)", flash)
        if panic["level"] in ("PANIC", "EXTREME"):
            await log_event("PANIC", "HIGH", symbol,
                            f"{panic['level']} panic (sell {panic['panic_sell']}/buy {panic['panic_buy']})", panic)
        if large_tx["classification"] in ("VERY_LARGE", "EXTREME"):
            await log_event("LARGE_TX", "MEDIUM", symbol,
                            f"{large_tx['classification']} transaction side {large_tx['side']}", large_tx)
        return snap

    # -------- main scan loop --------
    async def _scan_loop(self):
        while self._running:
            try:
                self._roll_daily()
                mode = self.cfg["mode"]
                symbols = (self.cfg["futures_symbols"] if mode != "spot" else self.cfg["spot_symbols"])
                if mode == "off":
                    symbols = self.cfg["futures_symbols"]  # still analyze for intel

                if self.status == "ACTIVE":
                    self.state = "ANALYZING"

                # BTC trend as market-wide reference
                btc_trend_ta = None
                try:
                    btc_c = await self._candles("BTCUSD", self.cfg["timeframes"]["trend"])
                    btc_trend_ta = ind.compute_ta(btc_c)
                except DeltaError:
                    pass

                market_wide = self._market_wide()
                for symbol in symbols:
                    if symbol not in self.products_by_symbol:
                        continue
                    snap = await self.analyze_symbol(symbol, mode, btc_trend_ta)
                    if not snap:
                        continue
                    await feed_push(
                        f"{symbol} analyzed → {snap['decision']['action']} "
                        f"(conf {snap['decision']['confidence']}, regime {snap['regime']})",
                        "analyze", symbol)
                    if self.status == "ACTIVE" and mode in ("spot", "futures"):
                        await self._maybe_trade(snap, mode, market_wide)
                    await self._manage_positions(snap, mode)

                if self.status == "ACTIVE":
                    self.state = "WAITING"
                # data freshness check
                if time.time() - self.last_md_ts > 60 and self.last_md_ts:
                    self.conn["market_data"] = "STALE"
            except Exception as e:
                logger.exception("scan loop error: %s", e)
            await asyncio.sleep(max(5, self.cfg.get("scan_interval_sec", 12)))

    def _market_wide(self):
        biases = []
        for s, snap in self.analysis.items():
            d = snap.get("direction")
            if d:
                biases.append(d)
        if not biases:
            return "NEUTRAL"
        b = biases.count("bullish"); be = biases.count("bearish")
        if be >= max(3, len(biases) * 0.7):
            return "MARKET_WIDE_PANIC"
        if b >= max(3, len(biases) * 0.7):
            return "MARKET_WIDE_EUPHORIA"
        return "MIXED"

    # -------- trade decision + execution --------
    async def _maybe_trade(self, snap, mode, market_wide):
        d = snap["decision"]
        symbol = snap["symbol"]
        if d["action"] in ("NO_TRADE", "HOLD"):
            return
        if d["action"] not in ("OPEN_LONG", "OPEN_SHORT", "BUY"):
            return  # closes handled by position manager
        # daily loss protection
        unreal = self._unrealized_total()
        if self.daily["realized_pnl"] + unreal <= -abs(self.cfg["risk"]["max_daily_loss_usd"]):
            await self._pause("Daily loss limit reached")
            return
        # cooldowns
        in_cd = False
        if symbol in self.cooldowns and time.time() < self.cooldowns[symbol]:
            in_cd = True
        if time.time() - self.last_trade_ts < self.cfg["risk"]["trade_cooldown_sec"]:
            in_cd = True
        recent_hour = [t for t in self.daily["trades_this_hour"] if time.time() - t < 3600]
        if len(recent_hour) >= self.cfg["risk"]["max_trades_per_hour"]:
            in_cd = True

        ta = snap["ta"]["entry"]
        price = ta["price"]
        direction = "long" if d["action"] in ("OPEN_LONG", "BUY") else "short"
        stop, take, stop_dist_pct, rr = compute_stop_take(
            price, direction, ta.get("atr"), snap["structure"], self.cfg["risk"]["min_risk_reward"])

        product = self.products_by_symbol[symbol]
        contract_value = product.get("contract_value", 1)
        equity = self.account["equity"] or 0.0
        contracts, notional = self.sizer.size(
            equity, self.cfg["risk"]["max_risk_per_trade_pct"], stop_dist_pct, price,
            contract_value, self.cfg["risk"]["max_position_size_usd"], self.cfg["risk"]["max_leverage"])

        expected_move_pct = abs(take - price) / price * 100
        fees = self.fee_engine.estimate(notional, expected_move_pct)

        ctx = {
            "confidence": d["confidence"], "risk_reward": rr, "fees": fees,
            "slippage_pct": self.cfg["fees"]["slippage_pct"] * 100,
            "open_positions": len([p for p in self.positions if p.get("size")]),
            "notional_usd": notional, "leverage": min(self.cfg["risk"]["max_leverage"], 5),
            "daily_loss": max(0.0, -(self.daily["realized_pnl"] + unreal)),
            "daily_trades": self.daily["trades"], "consecutive_losses": self.daily["consecutive_losses"],
            "in_cooldown": in_cd, "contracts": contracts,
            "data_fresh": self.conn["market_data"] == "LIVE",
            "time_synced": client.time_synced,
        }
        approved, fails = self.risk_engine.validate(self.cfg, ctx)

        # LLM advisory (may veto)
        ctx_text = "\n".join(d["reasons"]) + f"\nR:R {rr}, net edge {fees['net_pct']}%, market {market_wide}"
        llm = await dec.llm_reasoning(self.cfg, d, ctx_text)
        if llm.get("veto"):
            approved = False
            fails.append("LLM veto: contradictory/dangerous context")

        decision_log = {
            "symbol": symbol, "mode": mode, "action": d["action"], "price": price,
            "regime": snap["regime"], "confidence": d["confidence"], "bull_score": d["bull_score"],
            "components": d["components"], "risk_reward": rr, "stop": stop, "take": take,
            "notional_usd": notional, "contracts": contracts, "fees": fees,
            "expected_net_profit": fees["expected_net"], "reasons": d["reasons"],
            "risk_approved": approved, "risk_fails": fails, "market_wide": market_wide,
            "llm_narrative": llm.get("narrative"), "result": "PENDING",
        }

        if not approved:
            decision_log["result"] = "NO_TRADE"
            await log_decision(decision_log)
            await feed_push(f"{symbol} {d['action']} BLOCKED: {'; '.join(fails[:2])}", "risk", symbol)
            return

        # EXECUTE
        self.state = "EXECUTING"
        side = "buy" if direction == "long" else "sell"
        await feed_push(f"Risk check passed → executing {d['action']} {symbol}", "exec", symbol)
        res = await self.exec_engine.submit(
            self.cfg, symbol, side, contracts, mode, reduce_only=False,
            meta={"stop": stop, "take": take, "direction": direction, "entry": price})
        if res.get("ok"):
            self.daily["trades"] += 1
            self.daily["trades_this_hour"].append(time.time())
            self.last_trade_ts = time.time()
            self.cooldowns[symbol] = time.time() + self.cfg["risk"]["symbol_cooldown_sec"]
            decision_log["result"] = "EXECUTED"
            await feed_push(f"Fill pending confirmation for {symbol} {d['action']}", "exec", symbol)
            await self.notify(
                f"🟢 <b>OPENED {d['action'].replace('_',' ')}</b> {symbol}\n"
                f"size {contracts} @ ~{price}\nSL {stop} · TP {take} · R:R {rr}\n"
                f"confidence {d['confidence']}% · regime {snap['regime']}")
        else:
            decision_log["result"] = "EXEC_FAILED"
            decision_log["exec_error"] = res.get("error")
        await log_decision(decision_log)
        self.state = "WAITING"

    async def _manage_positions(self, snap, mode):
        symbol = snap["symbol"]
        pos = next((p for p in self.positions
                    if self.products_by_id.get(p.get("product_id"), {}).get("symbol") == symbol), None)
        if not pos or not pos.get("size"):
            return
        if self.status == "ACTIVE":
            self.state = "MANAGING"
        mark = self.mark_prices.get(symbol, snap["price"])
        ev = self.pos_manager.evaluate(self.cfg, pos, mark, snap["ta"]["entry"], snap["decision"], snap["panic"])
        if ev["decision"] in ("CLOSE", "TAKE_PROFIT", "REDUCE"):
            await feed_push(f"Position {symbol}: {ev['decision']} — {'; '.join(ev['reasons'])}", "manage", symbol)
            if self.cfg.get("live_trading") and self.status == "ACTIVE":
                size = abs(int(pos["size"]))
                if ev["decision"] == "REDUCE":
                    size = max(1, size // 2)
                side = "sell" if pos["size"] > 0 else "buy"
                await self.exec_engine.submit(self.cfg, symbol, side, size, mode, reduce_only=True,
                                              meta={"reason": ev["decision"]})

    def _unrealized_total(self):
        total = 0.0
        for p in self.positions:
            sym = self.products_by_id.get(p.get("product_id"), {}).get("symbol")
            entry = float(p.get("entry_price") or 0)
            size = float(p.get("size") or 0)
            mark = self.mark_prices.get(sym, entry)
            cv = self.products_by_id.get(p.get("product_id"), {}).get("contract_value", 1)
            if entry and size:
                total += (mark - entry) * size * float(cv or 1)
        return round(total, 4)

    # -------- reconciliation loop --------
    async def _reconcile_loop(self):
        # initial recovery reconcile
        await asyncio.sleep(2)
        while self._running:
            try:
                out = await reconcile(self.products_by_id)
                if out["balances"] is not None:
                    self.account = compute_equity(out["balances"])
                    self.conn["account"] = "LIVE"
                else:
                    self.conn["account"] = "ERROR"
                self.conn["required_ip"] = client.required_ip
                self.positions = out["positions"] or []
                self.open_orders = out["open_orders"] or []
                self.recent_fills = out["fills"] or []
                self.conn["time_synced"] = client.time_synced
                self.conn["server_time_drift"] = round(client.time_drift_sec, 3)
                if not out["errors"]:
                    if self.conn["rest"] != "CONNECTED":
                        self.conn["rest"] = "CONNECTED"
                # AUTO-RESUME after restart recovery (once reconciled)
                if (not getattr(self, "_auto_resume_done", False)
                        and self.cfg.get("auto_resume")
                        and self.cfg.get("live_trading") and self.cfg.get("mode") != "off"
                        and self.status == "PAUSED"
                        and (self.paused_reason or "").startswith("Restarted")
                        and self.conn["rest"] == "CONNECTED"):
                    self._auto_resume_done = True
                    self.status = "ACTIVE"
                    self.state = "ANALYZING"
                    self.paused_reason = None
                    await log_audit("auto_resume", {"reason": "restart recovery reconciled"})
                    await feed_push("AUTO-RESUME: reconciled after restart — autonomous trading live", "system")
                    await self.notify("🔄 <b>Auto-resumed</b> after restart — bot is live and trading again.")
            except Exception as e:
                logger.exception("reconcile error: %s", e)
                self.conn["account"] = "ERROR"
            await asyncio.sleep(15)

    async def _news_loop(self):
        while self._running:
            try:
                await news_engine.refresh()
                self.conn["news"] = "LIVE" if news_engine.available else "UNAVAILABLE"
            except Exception as e:
                logger.warning("news loop: %s", e)
                self.conn["news"] = "ERROR"
            await asyncio.sleep(180)

    # -------- websockets --------
    async def _public_ws_loop(self):
        backoff = 1
        while self._running:
            try:
                symbols = list(set(self.cfg["futures_symbols"] + ["BTCUSD"]))
                async with websockets.connect(WS_PUBLIC, ping_interval=20, ping_timeout=15) as ws:
                    self.conn["ws_public"] = "CONNECTED"
                    backoff = 1
                    await ws.send(json.dumps({"type": "subscribe", "payload": {"channels": [
                        {"name": "ticker", "symbols": symbols}]}}))
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("type") == "ticker" and msg.get("symbol"):
                            mp = msg.get("mark_price") or msg.get("close") or msg.get("spot_price")
                            if mp:
                                self.mark_prices[msg["symbol"]] = float(mp)
            except Exception as e:
                self.conn["ws_public"] = "ERROR"
                logger.warning("public ws: %s", e)
                await asyncio.sleep(min(backoff, 30))
                backoff *= 2

    async def _private_ws_loop(self):
        backoff = 1
        while self._running:
            try:
                async with websockets.connect(WS_PRIVATE, ping_interval=20, ping_timeout=15) as ws:
                    ts = str(int(time.time()))
                    sig = hmac.new(SECRET.encode(), ("GET" + ts + "/live").encode(), hashlib.sha256).hexdigest()
                    await ws.send(json.dumps({"type": "key-auth", "payload": {
                        "api-key": KEY, "signature": sig, "timestamp": ts}}))
                    authed = False
                    async for raw in ws:
                        msg = json.loads(raw)
                        mtype = msg.get("type")
                        if mtype in ("key-auth", "auth"):
                            if msg.get("success") or msg.get("message") == "Authenticated":
                                authed = True
                                self.conn["ws_private"] = "CONNECTED"
                                await ws.send(json.dumps({"type": "subscribe", "payload": {"channels": [
                                    {"name": "positions", "symbols": ["all"]},
                                    {"name": "orders", "symbols": ["all"]},
                                    {"name": "v2/user_trades", "symbols": ["all"]},
                                    {"name": "margins"}]}}))
                            else:
                                self.conn["ws_private"] = "ERROR"
                                break
                        elif mtype == "orders" and msg.get("reason") == "fill":
                            await feed_push(f"WS fill: {msg.get('symbol')} {msg.get('side')} "
                                            f"@ {msg.get('average_fill_price')}", "exec", msg.get("symbol", ""))
                    if not authed:
                        self.conn["ws_private"] = "ERROR"
            except Exception as e:
                self.conn["ws_private"] = "ERROR"
                logger.warning("private ws: %s", e)
            await asyncio.sleep(min(backoff, 30))
            backoff = min(backoff * 2, 30)

    # -------- control actions --------
    async def set_mode(self, mode):
        assert mode in ("off", "spot", "futures")
        prev = self.cfg["mode"]
        if prev != mode and prev in ("spot", "futures"):
            # stop new entries on switch; keep positions
            self.status = "PAUSED"
            self.state = "PAUSED"
            self.paused_reason = f"Mode switched {prev}→{mode}; new entries stopped. Existing positions preserved."
        self.cfg["mode"] = mode
        await save_config(self.cfg)
        await log_audit("set_mode", {"from": prev, "to": mode})
        await feed_push(f"Trading mode set to {mode.upper()}", "system")
        return self.cfg

    async def set_live(self, enabled):
        self.cfg["live_trading"] = bool(enabled)
        await save_config(self.cfg)
        await log_audit("set_live", {"enabled": enabled})
        await feed_push(f"LIVE autonomous trading {'ENABLED' if enabled else 'DISABLED'}", "system")
        if not enabled and self.status == "ACTIVE":
            await self._pause("Live trading disabled by user")
        return self.cfg

    async def resume(self):
        if self.cfg["mode"] == "off":
            return {"ok": False, "error": "Select SPOT or FUTURES first"}
        if not self.cfg["live_trading"]:
            return {"ok": False, "error": "Enable LIVE autonomous trading first"}
        if self.conn["rest"] != "CONNECTED":
            return {"ok": False, "error": "Delta REST not connected — cannot resume"}
        self.status = "ACTIVE"
        self.state = "ANALYZING"
        self.paused_reason = None
        await log_audit("resume", {})
        await feed_push("Autonomous trading RESUMED — bot is now live", "system")
        return {"ok": True}

    async def _pause(self, reason):
        self.status = "PAUSED"
        self.state = "PAUSED"
        self.paused_reason = reason
        await log_audit("pause", {"reason": reason})
        await feed_push(f"KILL SWITCH / PAUSE: {reason}", "system")

    async def stop(self, reason="Manual stop"):
        await self._pause(reason)
        return {"ok": True}

    async def emergency_cancel_orders(self):
        results = []
        for sym in set(self.cfg["futures_symbols"] + self.cfg["spot_symbols"]):
            pid = self.products_by_symbol.get(sym, {}).get("id")
            if not pid:
                continue
            try:
                await client.cancel_all(product_id=pid)
                results.append({"symbol": sym, "ok": True})
            except DeltaError as e:
                results.append({"symbol": sym, "ok": False, "error": e.payload})
        await log_audit("emergency_cancel_orders", {"results": results})
        await feed_push("EMERGENCY: cancel all open orders requested", "system")
        return results

    async def emergency_close_positions(self):
        results = []
        for p in self.positions:
            if not p.get("size"):
                continue
            sym = self.products_by_id.get(p["product_id"], {}).get("symbol")
            side = "sell" if p["size"] > 0 else "buy"
            try:
                res = await client.place_order(product_id=p["product_id"], size=abs(int(p["size"])),
                                                side=side, order_type="market_order", reduce_only=True,
                                                client_order_id=gen_client_order_id())
                results.append({"symbol": sym, "ok": True, "order": res})
            except DeltaError as e:
                results.append({"symbol": sym, "ok": False, "error": e.payload})
        await self._pause("Emergency close executed")
        await log_audit("emergency_close_positions", {"results": results})
        return results

    async def protect_position(self, symbol, stop_pct=1.0, take_pct=2.0):
        pos = next((p for p in self.positions
                    if self.products_by_id.get(p.get("product_id"), {}).get("symbol") == symbol), None)
        if not pos or not pos.get("size"):
            return {"ok": False, "error": f"no open position for {symbol}"}
        entry = float(pos.get("entry_price") or self.mark_prices.get(symbol, 0))
        if not entry:
            return {"ok": False, "error": "no entry price"}
        long_pos = pos["size"] > 0
        if long_pos:
            stop = entry * (1 - stop_pct / 100)
            take = entry * (1 + take_pct / 100)
        else:
            stop = entry * (1 + stop_pct / 100)
            take = entry * (1 - take_pct / 100)
        return await self.exec_engine.attach_bracket(symbol, stop, take)

    def snapshot(self):
        return {
            "status": self.status, "state": self.state, "mode": self.cfg["mode"],
            "live_trading": self.cfg["live_trading"], "paused_reason": self.paused_reason,
            "connection": self.conn, "account": self.account,
            "unrealized_pnl": self._unrealized_total(),
            "daily": {"date": self.daily["date"], "trades": self.daily["trades"],
                      "realized_pnl": self.daily["realized_pnl"],
                      "consecutive_losses": self.daily["consecutive_losses"]},
            "open_positions": len([p for p in self.positions if p.get("size")]),
            "open_orders_count": len(self.open_orders),
            "market_wide": self._market_wide(),
        }


bot = Bot()
