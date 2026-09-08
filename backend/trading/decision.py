"""Decision, risk, position-sizing, fee & sentiment engines.

Deterministic code owns risk, sizing, validation & limits. The LLM (if enabled)
only produces advisory reasoning and may VETO a trade — it can never force one
nor relax a risk limit.
"""
import os
import logging

logger = logging.getLogger("dacte.decision")


def sentiment_score(news_score, ta_trend, orderflow, funding=None):
    """Normalized -100..100 sentiment. Reports which sources were available."""
    parts = []
    total = 0.0
    wsum = 0.0
    sources = {}
    if news_score is not None:
        total += news_score * 0.4; wsum += 0.4; sources["news"] = "LIVE"
        parts.append(("news", news_score))
    else:
        sources["news"] = "UNAVAILABLE"
    if ta_trend:
        b = ta_trend.get("technical_score", 50)
        val = (b - 50) * 2
        total += val * 0.3; wsum += 0.3; sources["btc_trend"] = "LIVE"
        parts.append(("trend", val))
    if orderflow and orderflow.get("available"):
        total += orderflow["orderflow_score"] * 0.3; wsum += 0.3; sources["orderflow"] = "LIVE"
        parts.append(("orderflow", orderflow["orderflow_score"]))
    else:
        sources["orderflow"] = "UNAVAILABLE"
    sources["social_x"] = "UNAVAILABLE"  # no authenticated X/Twitter API key provided
    score = round(total / wsum, 1) if wsum else 0
    return max(-100, min(100, score)), sources


class FeeEngine:
    def __init__(self, fees):
        self.taker = fees.get("taker", 0.0005)
        self.maker = fees.get("maker", 0.0002)
        self.slip = fees.get("slippage_pct", 0.0005)

    def estimate(self, notional, expected_move_pct):
        entry_fee = notional * self.taker
        exit_fee = notional * self.taker
        slippage = notional * self.slip
        gross = notional * abs(expected_move_pct) / 100
        net = gross - entry_fee - exit_fee - slippage
        return {
            "entry_fee": round(entry_fee, 4), "exit_fee": round(exit_fee, 4),
            "slippage": round(slippage, 4), "expected_gross": round(gross, 4),
            "expected_net": round(net, 4),
            "net_pct": round(net / notional * 100, 4) if notional else 0,
        }


class PositionSizer:
    def size(self, equity_usd, risk_pct, stop_distance_pct, price, contract_value, max_pos_usd, max_lev):
        """Returns (contracts, notional_usd)."""
        if stop_distance_pct <= 0:
            stop_distance_pct = 1.0
        risk_amount = equity_usd * risk_pct / 100
        notional = risk_amount / (stop_distance_pct / 100)
        notional = min(notional, max_pos_usd, equity_usd * max_lev)
        per_contract = price * float(contract_value or 1)
        contracts = int(notional / per_contract) if per_contract else 0
        return max(contracts, 0), round(notional, 2)


class RiskEngine:
    """Server-side, hard limits. AI cannot override."""

    def validate(self, cfg, ctx):
        r = cfg["risk"]
        fails = []
        if ctx["confidence"] < r["min_confidence"]:
            fails.append(f"confidence {ctx['confidence']} < min {r['min_confidence']}")
        if ctx["risk_reward"] < r["min_risk_reward"]:
            fails.append(f"R:R {ctx['risk_reward']} < min {r['min_risk_reward']}")
        if ctx["fees"]["net_pct"] < r["min_expected_net_profit_pct"]:
            fails.append(f"net edge {ctx['fees']['net_pct']}% < min {r['min_expected_net_profit_pct']}% (fees eat profit)")
        if ctx["slippage_pct"] > r["max_slippage_pct"]:
            fails.append(f"slippage {ctx['slippage_pct']}% > max {r['max_slippage_pct']}%")
        if ctx["open_positions"] >= r["max_open_positions"]:
            fails.append(f"open positions {ctx['open_positions']} >= max {r['max_open_positions']}")
        if ctx["notional_usd"] > r["max_position_size_usd"] + 1e-6:
            fails.append(f"size ${ctx['notional_usd']} > max ${r['max_position_size_usd']}")
        if ctx["leverage"] > r["max_leverage"]:
            fails.append(f"leverage {ctx['leverage']} > max {r['max_leverage']}")
        if ctx["daily_loss"] >= r["max_daily_loss_usd"]:
            fails.append(f"daily loss ${ctx['daily_loss']} >= max ${r['max_daily_loss_usd']}")
        if ctx["daily_trades"] >= r["max_daily_trades"]:
            fails.append(f"daily trades {ctx['daily_trades']} >= max {r['max_daily_trades']}")
        if ctx["consecutive_losses"] >= r["max_consecutive_losses"]:
            fails.append(f"consecutive losses {ctx['consecutive_losses']} >= max {r['max_consecutive_losses']}")
        if ctx.get("in_cooldown"):
            fails.append("symbol/trade cooldown active")
        if ctx["contracts"] < 1:
            fails.append("computed size < 1 contract (insufficient equity for risk)")
        if not ctx.get("data_fresh", True):
            fails.append("market data stale")
        if not ctx.get("time_synced", True):
            fails.append("server clock drift — trading blocked")
        return (len(fails) == 0), fails


class DecisionEngine:
    """Weighted, transparent scoring -> action + confidence + reasons."""

    def decide(self, cfg, symbol, mode, ta_multi, structure, regime, orderflow,
               sentiment, news_score, panic, large_tx, position):
        w = cfg["weights"]
        ta_entry = ta_multi["entry"]
        ta_trend = ta_multi["trend"]
        align_score, direction = ta_multi["alignment_score"], ta_multi["direction"]

        def norm(x):  # -100..100 -> 0..100 bull
            return (x + 100) / 2

        comp = {
            "technical": ta_entry["technical_score"] if ta_entry else 50,
            "structure": structure["structure_score"],
            "volume": min(100, (ta_entry.get("volume_ratio", 1) if ta_entry else 1) * 33),
            "sentiment": norm(sentiment),
            "news": norm(news_score if news_score is not None else 0),
            "regime": {"TRENDING_UP": 80, "BREAKOUT": 78, "TRENDING_DOWN": 20, "BREAKDOWN": 22,
                       "RANGING": 50, "HIGH_VOLATILITY": 45, "LOW_VOLATILITY": 48,
                       "UNCERTAIN": 45}.get(regime, 50),
            "orderflow": norm(orderflow["orderflow_score"]) if orderflow and orderflow.get("available") else 50,
        }
        wsum = sum(w.values()) or 1
        bull_score = sum(comp[k] * w.get(k, 0) for k in comp) / wsum  # 0..100
        # directional confidence: distance from 50
        confidence = round(abs(bull_score - 50) * 2, 1)
        confidence = min(confidence, 100)

        reasons = []
        reasons.append(f"MTF alignment {align_score} ({direction})")
        reasons.append(f"regime {regime}")
        if ta_entry:
            reasons.append(f"technical {ta_entry['technical_score']}/100 (RSI {ta_entry.get('rsi')})")
        reasons.append(f"structure {structure['label']} {structure['structure_score']}/100")
        if orderflow and orderflow.get("available"):
            reasons.append(f"orderflow {orderflow['orderflow_score']}")
        reasons.append(f"sentiment {sentiment}")
        if news_score is not None:
            reasons.append(f"news {news_score}")
        reasons.append(f"panic {panic['level']} (sell {panic['panic_sell']}/buy {panic['panic_buy']})")
        if large_tx and large_tx["classification"] != "NORMAL":
            reasons.append(f"large tx {large_tx['classification']} side {large_tx['side']}")

        bullish = bull_score >= 58 and direction != "bearish"
        bearish = bull_score <= 42 and direction != "bullish"

        # Panic gating — never auto trade a panic; require confluence
        if panic["level"] in ("PANIC", "EXTREME"):
            reasons.append("panic regime → demand extra confluence")
            confidence = max(0, confidence - 15)

        action = "NO_TRADE"
        if position and position.get("size", 0) != 0:
            # management context handled elsewhere; here suggest HOLD unless reversal
            long_pos = position["size"] > 0
            if long_pos and bearish:
                action = "CLOSE_LONG" if mode == "futures" else "SELL"
            elif (not long_pos) and bullish:
                action = "CLOSE_SHORT"
            else:
                action = "HOLD"
        else:
            if mode == "spot":
                action = "BUY" if bullish else "NO_TRADE"
            elif mode == "futures":
                if bullish:
                    action = "OPEN_LONG"
                elif bearish:
                    action = "OPEN_SHORT"
                else:
                    action = "NO_TRADE"
        return {
            "symbol": symbol, "mode": mode, "action": action,
            "confidence": confidence, "bull_score": round(bull_score, 1),
            "direction": direction, "components": {k: round(v, 1) for k, v in comp.items()},
            "reasons": reasons,
        }


async def llm_reasoning(cfg, decision, context_text):
    """Advisory narrative + optional veto. Failure is non-fatal."""
    if not cfg.get("use_llm_reasoning"):
        return {"narrative": None, "veto": False}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ["EMERGENT_LLM_KEY"]
        provider = os.environ.get("DECISION_LLM_PROVIDER", "anthropic")
        model = os.environ.get("DECISION_LLM_MODEL", "claude-sonnet-4-6")
        chat = LlmChat(
            api_key=key,
            session_id=f"dacte-{decision['symbol']}",
            system_message=(
                "You are a risk-first crypto trading analyst. Given quantitative signals, "
                "write a concise 2-3 sentence rationale. You may VETO a trade if the context is "
                "contradictory or dangerous, but you cannot force a trade or change risk limits. "
                "Respond as: VERDICT: <AGREE|VETO> | <one short paragraph>."
            ),
        ).with_model(provider, model)
        msg = UserMessage(text=(
            f"Proposed action: {decision['action']} on {decision['symbol']} "
            f"(confidence {decision['confidence']}, bull_score {decision['bull_score']}).\n"
            f"Signals:\n{context_text}\n\nGive VERDICT and rationale."
        ))
        resp = await chat.send_message(msg)
        text = resp if isinstance(resp, str) else str(resp)
        veto = "VETO" in text.split("|")[0].upper()
        return {"narrative": text.strip()[:600], "veto": veto}
    except Exception as e:
        logger.warning("LLM reasoning skipped: %s", e)
        return {"narrative": None, "veto": False}
