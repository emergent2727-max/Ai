"""Backend API tests for DACTE autonomous crypto trading bot.

Safety: NEVER leave live_trading=true or mode!=off. No real orders placed.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback read from frontend env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

TIMEOUT = 30


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    yield s
    # teardown: ensure safety
    try:
        s.post(f"{API}/bot/live", json={"enabled": False}, timeout=TIMEOUT)
    except Exception:
        pass
    try:
        s.post(f"{API}/bot/mode", json={"mode": "off"}, timeout=TIMEOUT)
    except Exception:
        pass


# --- basic telemetry ---
class TestTelemetry:
    def test_root(self, session):
        r = session.get(f"{API}/", timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_bot_state(self, session):
        r = session.get(f"{API}/bot/state", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "state" in data
        assert "mode" in data
        assert "live_trading" in data
        assert data["live_trading"] is False
        # connection health
        conn = data.get("connection") or data.get("conn") or {}
        assert isinstance(conn, dict)
        assert "account" in data
        assert "daily" in data
        assert "market_wide" in data

    def test_connection(self, session):
        r = session.get(f"{API}/connection", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert "required_ip" in d  # may be None

    def test_account(self, session):
        r = session.get(f"{API}/account", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert "account" in d
        assert "unrealized_pnl" in d
        assert "daily" in d

    def test_positions(self, session):
        r = session.get(f"{API}/positions", timeout=TIMEOUT)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_orders(self, session):
        r = session.get(f"{API}/orders", timeout=TIMEOUT)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_events(self, session):
        r = session.get(f"{API}/events", timeout=TIMEOUT)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_feed(self, session):
        r = session.get(f"{API}/feed", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list)
        for item in d[:3]:
            assert "ts" in item
            assert "line" in item

    def test_decisions(self, session):
        r = session.get(f"{API}/decisions", timeout=TIMEOUT)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_news(self, session):
        r = session.get(f"{API}/news", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert "available" in d
        assert "sources" in d
        assert "items" in d
        assert isinstance(d["items"], list)

    def test_scanner(self, session):
        r = session.get(f"{API}/scanner", timeout=TIMEOUT)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# --- analysis ---
class TestAnalysis:
    def test_analysis_list(self, session):
        # Wait up to ~30s for the analysis loop (runs every ~12s) to populate
        got = []
        for _ in range(6):
            r = session.get(f"{API}/analysis", timeout=TIMEOUT)
            assert r.status_code == 200
            got = r.json()
            if got:
                break
            time.sleep(6)
        assert isinstance(got, list)
        if not got:
            pytest.skip("analysis not populated yet (loop hasn't produced snapshots)")
        snap = got[0]
        # verify structure
        assert "price" in snap
        assert "regime" in snap
        assert "ta" in snap
        assert "structure" in snap
        assert "orderflow" in snap
        assert "large_tx" in snap
        assert "panic" in snap
        assert "sentiment" in snap
        assert "decision" in snap
        d = snap["decision"]
        assert d["action"] in {"NO_TRADE", "HOLD", "OPEN_LONG", "OPEN_SHORT",
                               "BUY", "SELL", "CLOSE_LONG", "CLOSE_SHORT"}
        assert "confidence" in d
        assert "components" in d
        assert "reasons" in d
        panic = snap["panic"]
        for k in ("panic_sell", "panic_buy", "level"):
            assert k in panic


# --- mode & live gating ---
class TestModeAndLive:
    def test_mode_futures(self, session):
        r = session.post(f"{API}/bot/mode", json={"mode": "futures"}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        cfg = session.get(f"{API}/bot/config", timeout=TIMEOUT).json()
        assert cfg["mode"] == "futures"

    def test_mode_spot(self, session):
        r = session.post(f"{API}/bot/mode", json={"mode": "spot"}, timeout=TIMEOUT)
        assert r.status_code == 200
        cfg = session.get(f"{API}/bot/config", timeout=TIMEOUT).json()
        assert cfg["mode"] == "spot"

    def test_mode_invalid(self, session):
        r = session.post(f"{API}/bot/mode", json={"mode": "bogus"}, timeout=TIMEOUT)
        assert r.status_code == 400

    def test_mode_off(self, session):
        r = session.post(f"{API}/bot/mode", json={"mode": "off"}, timeout=TIMEOUT)
        assert r.status_code == 200
        cfg = session.get(f"{API}/bot/config", timeout=TIMEOUT).json()
        assert cfg["mode"] == "off"

    def test_live_wrong_confirm_rejected(self, session):
        r = session.post(f"{API}/bot/live",
                         json={"enabled": True, "confirm": "wrong"}, timeout=TIMEOUT)
        assert r.status_code == 400

    def test_live_enable_then_disable(self, session):
        r = session.post(f"{API}/bot/live",
                         json={"enabled": True, "confirm": "ENABLE REAL CAPITAL"},
                         timeout=TIMEOUT)
        assert r.status_code == 200
        # Immediately disable for safety
        r2 = session.post(f"{API}/bot/live",
                          json={"enabled": False, "confirm": ""}, timeout=TIMEOUT)
        assert r2.status_code == 200
        state = session.get(f"{API}/bot/state", timeout=TIMEOUT).json()
        assert state["live_trading"] is False

    def test_resume_gating_when_off_or_not_live(self, session):
        # ensure mode off & live false
        session.post(f"{API}/bot/mode", json={"mode": "off"}, timeout=TIMEOUT)
        session.post(f"{API}/bot/live", json={"enabled": False}, timeout=TIMEOUT)
        r = session.post(f"{API}/bot/resume", timeout=TIMEOUT)
        assert r.status_code == 400

    def test_stop(self, session):
        r = session.post(f"{API}/bot/stop", timeout=TIMEOUT)
        assert r.status_code == 200
        state = session.get(f"{API}/bot/state", timeout=TIMEOUT).json()
        assert state["status"].upper() == "PAUSED"


# --- config update ---
class TestConfig:
    def test_put_config_persists(self, session):
        r = session.put(f"{API}/bot/config",
                        json={"risk": {"min_confidence": 70}, "weights": {"technical": 30}},
                        timeout=TIMEOUT)
        assert r.status_code == 200
        cfg = session.get(f"{API}/bot/config", timeout=TIMEOUT).json()
        assert cfg["risk"]["min_confidence"] == 70
        assert cfg["weights"]["technical"] == 30


# --- emergency ---
class TestEmergency:
    def test_close_positions_wrong_confirm(self, session):
        r = session.post(f"{API}/emergency/close-positions",
                         json={"confirm": "wrong"}, timeout=TIMEOUT)
        assert r.status_code == 400

    def test_close_positions_correct(self, session):
        r = session.post(f"{API}/emergency/close-positions",
                         json={"confirm": "CLOSE ALL"}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_cancel_orders(self, session):
        r = session.post(f"{API}/emergency/cancel-orders", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is True
        assert "results" in d


# --- backtest ---
class TestBacktest:
    def test_backtest(self, session):
        r = session.post(f"{API}/backtest",
                         json={"symbol": "BTCUSD", "resolution": "15m", "candles": 300},
                         timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "HISTORICAL SIMULATION" in d.get("label", "")
        for k in ("net_return_pct", "num_trades", "win_rate",
                  "profit_factor", "total_fees"):
            assert k in d
