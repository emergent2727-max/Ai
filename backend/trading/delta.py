"""Delta Exchange India REST client — production, signed (HMAC-SHA256).

Auth prehash: method + timestamp + path + query_string + body   (docs.delta.exchange)
Never logs the secret. Uses fresh timestamp per request (5s server window).
"""
import hashlib
import hmac
import json
import os
import time
import logging
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger("dacte.delta")

BASE = os.environ["DELTA_BASE_URL"]
KEY = os.environ["DELTA_API_KEY"]
SECRET = os.environ["DELTA_API_SECRET"]
UA = "dacte-autonomous-bot"


def _sign(message: str) -> str:
    return hmac.new(SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()


class DeltaError(Exception):
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        super().__init__(f"Delta API error {status}: {payload}")


class DeltaClient:
    def __init__(self):
        self._client = httpx.AsyncClient(base_url=BASE, timeout=httpx.Timeout(15.0))
        self.time_drift_sec = 0.0
        self.time_synced = True
        self.required_ip = None  # populated if ip_not_whitelisted error seen

    async def close(self):
        await self._client.aclose()

    def _headers(self, method: str, path: str, query: str, body: str) -> dict:
        ts = str(int(time.time()))
        prehash = method + ts + path + query + body
        return {
            "api-key": KEY,
            "timestamp": ts,
            "signature": _sign(prehash),
            "User-Agent": UA,
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, params: dict = None, body: dict = None, signed: bool = False):
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        body_str = json.dumps(body, separators=(",", ":")) if body is not None else ""
        headers = {"User-Agent": UA, "Content-Type": "application/json"}
        if signed:
            if not self.time_synced:
                raise DeltaError(0, {"error": {"code": "clock_drift_blocked"}})
            headers = self._headers(method, path, query, body_str)
        url = path + query
        try:
            resp = await self._client.request(method, url, headers=headers, content=body_str or None)
        except httpx.HTTPError as e:
            raise DeltaError(0, {"error": {"code": "network_error", "detail": str(e)}})
        # opportunistic time drift check from server Date header
        self._update_drift(resp)
        try:
            data = resp.json()
        except Exception:
            raise DeltaError(resp.status_code, {"error": {"code": "bad_response", "text": resp.text[:200]}})
        if resp.status_code >= 400 or (isinstance(data, dict) and data.get("success") is False):
            err = data.get("error") if isinstance(data, dict) else data
            if isinstance(err, dict) and err.get("code") == "ip_not_whitelisted_for_api_key":
                ctx = err.get("context") or {}
                self.required_ip = ctx.get("client_ip") or ctx.get("ip")
            raise DeltaError(resp.status_code, data)
        if signed:
            self.required_ip = None  # signed request succeeded → whitelist OK
        return data.get("result") if isinstance(data, dict) else data

    def _update_drift(self, resp):
        date_hdr = resp.headers.get("Date")
        if not date_hdr:
            return
        try:
            server = parsedate_to_datetime(date_hdr)
            if server.tzinfo is None:
                server = server.replace(tzinfo=timezone.utc)
            drift = (datetime.now(timezone.utc) - server).total_seconds()
            self.time_drift_sec = drift
            self.time_synced = abs(drift) < 4.0
        except Exception:
            pass

    # ---- public market data ----
    async def get_products(self, contract_types=None, states="live"):
        params = {"states": states, "page_size": 1000}
        if contract_types:
            params["contract_types"] = contract_types
        return await self._request("GET", "/v2/products", params=params)

    async def get_tickers(self, contract_types=None):
        params = {}
        if contract_types:
            params["contract_types"] = contract_types
        return await self._request("GET", "/v2/tickers", params=params)

    async def get_ticker(self, symbol):
        return await self._request("GET", f"/v2/tickers/{symbol}")

    async def get_candles(self, symbol, resolution, count=200):
        end = int(time.time())
        span = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
                "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "1d": 86400}.get(resolution, 300)
        start = end - span * (count + 2)
        params = {"resolution": resolution, "symbol": symbol, "start": start, "end": end}
        rows = await self._request("GET", "/v2/history/candles", params=params)
        rows = sorted(rows or [], key=lambda r: r["time"])  # ascending
        return rows

    async def get_orderbook(self, symbol):
        return await self._request("GET", f"/v2/l2orderbook/{symbol}")

    async def get_trades(self, symbol):
        return await self._request("GET", f"/v2/trades/{symbol}")

    # ---- private / account ----
    async def get_balances(self):
        return await self._request("GET", "/v2/wallet/balances", signed=True)

    async def get_positions_margined(self):
        return await self._request("GET", "/v2/positions/margined", signed=True)

    async def get_orders(self, states="open"):
        return await self._request("GET", "/v2/orders", params={"states": states}, signed=True)

    async def get_fills(self, page_size=50):
        return await self._request("GET", "/v2/fills", params={"page_size": page_size}, signed=True)

    async def get_order_history(self, page_size=50):
        return await self._request("GET", "/v2/orders/history", params={"page_size": page_size}, signed=True)

    # ---- trading ----
    async def place_order(self, product_id, size, side, order_type="market_order",
                          limit_price=None, reduce_only=False, client_order_id=None,
                          time_in_force=None):
        body = {
            "product_id": int(product_id),
            "size": int(size),
            "side": side,
            "order_type": order_type,
        }
        if order_type == "limit_order" and limit_price is not None:
            body["limit_price"] = str(limit_price)
            body["time_in_force"] = time_in_force or "gtc"
        else:
            body["time_in_force"] = time_in_force or "ioc"
        if reduce_only:
            body["reduce_only"] = True
        if client_order_id:
            body["client_order_id"] = client_order_id[:32]
        return await self._request("POST", "/v2/orders", body=body, signed=True)

    async def cancel_order(self, product_id, order_id):
        body = {"id": int(order_id), "product_id": int(product_id)}
        return await self._request("DELETE", "/v2/orders", body=body, signed=True)

    async def cancel_all(self, product_id=None):
        body = {}
        if product_id:
            body["product_id"] = int(product_id)
        return await self._request("DELETE", "/v2/orders/all", body=body, signed=True)

    async def change_leverage(self, product_id, leverage):
        body = {"leverage": str(leverage)}
        return await self._request("POST", f"/v2/products/{int(product_id)}/orders/leverage",
                                   body=body, signed=True)

    async def place_bracket(self, product_id, product_symbol, stop_loss_price,
                            take_profit_price, tp_limit_price=None, trigger="mark_price"):
        """Attach exchange-native protective SL/TP bracket to an OPEN position."""
        body = {
            "product_id": int(product_id),
            "product_symbol": product_symbol,
            "stop_loss_order": {"order_type": "market_order", "stop_price": str(stop_loss_price)},
            "take_profit_order": {"order_type": "limit_order", "stop_price": str(take_profit_price),
                                   "limit_price": str(tp_limit_price or take_profit_price)},
            "bracket_stop_trigger_method": trigger,
        }
        return await self._request("POST", "/v2/orders/bracket", body=body, signed=True)


client = DeltaClient()
