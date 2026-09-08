"""Static defaults for the autonomous bot configuration."""

DEFAULT_CONFIG = {
    "_id": "bot_config",
    "mode": "off",                # off | spot | futures
    "live_trading": False,        # master real-money switch, default OFF
    # Liquid perpetual futures used for market intelligence + futures execution
    "futures_symbols": ["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD"],
    # Spot products (INR quoted) used for spot execution
    "spot_symbols": ["BTC_INR", "ETH_INR", "SOL_INR", "XRP_INR"],
    "timeframes": {"trend": "1h", "setup": "15m", "entry": "5m"},
    "scan_interval_sec": 12,
    "risk": {
        "max_risk_per_trade_pct": 0.5,      # % of equity risked per trade
        "max_position_size_usd": 100.0,
        "max_daily_loss_usd": 20.0,
        "max_daily_trades": 10,
        "max_open_positions": 3,
        "max_leverage": 5,
        "max_slippage_pct": 0.3,
        "min_expected_net_profit_pct": 0.3,  # net edge after fees required
        "min_confidence": 65,
        "min_risk_reward": 1.5,
        "max_consecutive_losses": 3,
        "trade_cooldown_sec": 300,
        "symbol_cooldown_sec": 900,
        "max_trades_per_hour": 4,
    },
    "weights": {
        "technical": 25,
        "structure": 20,
        "volume": 15,
        "sentiment": 10,
        "news": 10,
        "regime": 10,
        "orderflow": 10,
    },
    "fees": {"taker": 0.0005, "maker": 0.0002, "slippage_pct": 0.0005},
    "trailing_stop_enabled": True,
    "use_llm_reasoning": True,
    "telegram_chat_id": None,
    "alerts_enabled": True,
    "auto_resume": True,
}

BOT_STATES = ["ANALYZING", "WAITING", "SIGNAL", "EXECUTING", "MANAGING", "PAUSED"]
BOT_STATUS = ["ACTIVE", "PAUSED", "ERROR"]
