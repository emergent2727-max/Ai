# DACTE — Delta Autonomous Crypto Trading Engine

## Original problem statement
Build a complete AUTONOMOUS LIVE crypto trading bot on Delta Exchange India (production).
Not an exchange clone, not a manual terminal. The bot observes → analyzes → decides →
validates (risk) → executes → manages → exits. Real money, no paper/testnet/fake data.
User role: select mode (OFF/SPOT/FUTURES) → configure risk → enable bot → monitor.

## Architecture (implemented)
- **Backend** FastAPI (`/app/backend`), MongoDB (collections instead of Postgres, same schema intent).
  - `trading/delta.py` — signed REST client (HMAC-SHA256 method+ts+path+query+body), time-drift check, IP-whitelist surfacing.
  - `trading/indicators.py` — EMA9/21/50/200, RSI, MACD, VWAP, ATR, ADX, Bollinger, volume, swings, S/R; structure (HH/HL/LH/LL, breakout/breakdown); regime; multi-timeframe alignment.
  - `trading/analysis.py` — NewsEngine (NewsAPI + RSS, real, no fabrication), sentiment (-100..100 w/ source availability), order-flow, dynamic large-transaction detector, panic buy/sell, flash crash/pump.
  - `trading/decision.py` — weighted transparent DecisionEngine (configurable weights), FeeEngine (fee-aware net edge), PositionSizer, RiskEngine (hard server-side limits), optional LLM advisory/veto (Claude Sonnet 4.6 via Emergent Universal Key).
  - `trading/execution.py` — mode-gated execution (SPOT vs FUTURES enforced backend), idempotent client_order_id, ATR/structure SL/TP, PositionManager (hold/reduce/close/tp/trail), REST reconciliation, equity calc.
  - `trading/bot.py` — orchestrator: state machine (ANALYZING/WAITING/SIGNAL/EXECUTING/MANAGING/PAUSED), scan loop, reconcile loop, public WS (ticker) + private WS (key-auth, best-effort), news loop, kill switch, daily-loss protection, cooldowns, mode switch, restart recovery (starts PAUSED), emergency controls.
  - `server.py` — /api routes for state, config, mode, live, resume/stop, account, positions, orders, analysis, events, feed, decisions, news, connection, emergency, manual order, backtest.
- **Frontend** React tactical dark dashboard (`/app/frontend/src`): AutonomousStatusBar, ConnectionHealthBar, AccountMetrics, BotBrainAnalysis, LiveMarketEvents, DecisionTimelineFeed, PositionsAndOrders, RiskAndStrategyConfig, LiveTradingModal, EmergencyControls, NewsPanel. Polls every 2.5s.

## Integrations
- Delta Exchange India production REST + public WS (live). Private WS via key-auth (best-effort; REST reconciliation authoritative).
- NewsAPI.org + crypto RSS (live). LLM: Claude Sonnet 4.6 (advisory reasoning/veto only).

## Safety model
- Default TRADING OFF + LIVE OFF. Deterministic code owns risk/sizing/execution/limits; LLM cannot override.
- No fake data: unavailable sources show UNAVAILABLE. Capital protection > trade frequency; NO_TRADE is a valid outcome.

## Implemented (2026-09-08)
- Full first milestone: secure Delta connection, account/balance sync, live market data (candles/ticker/orderbook/trades), all analysis engines, autonomous decision + risk + fee-aware NO-TRADE, mode gate, execution path (dormant until enabled), dashboard, backtesting (historical EMA-cross simulation), restart recovery.

## Backlog / next (P1/P2)
- Exchange-native protective (bracket) orders for SL/TP.
- Strategy performance analytics UI (win rate, PF, drawdown by regime/symbol).
- Self-learning weight adaptation (safe params only) with user approval.
- Social/X sentiment source (needs API key) — currently UNAVAILABLE by design.
- Full private-WS live fills UI (currently REST reconciliation).
