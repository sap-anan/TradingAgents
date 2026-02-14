"""
Bitkub API Client - Low-level wrapper for Bitkub exchange
No external Bitkub library — pure requests + hmac + websockets

Bitkub API docs: https://github.com/bitkub/bitkub-official-api-docs

Public endpoints (no auth): ticker, trades, depth, symbols
Private endpoints (auth): balances, place-bid, place-ask, cancel, order-info
"""
import time
import json
import hmac
import hashlib
import requests
from typing import Dict, Any, Optional, List


class BitkubClient:
    """
    Low-level Bitkub API wrapper.

    Usage:
        # Public (no key needed)
        client = BitkubClient()
        client.ticker()
        client.trades(sym="THB_BTC")

        # Private (needs API key)
        client = BitkubClient(api_key="...", api_secret="...")
        client.balances()
        client.place_bid(sym="THB_BTC", amt=1000, rat=0, typ="market")
    """

    BASE_URL = "https://api.bitkub.com"

    # Rate limit: 100 req/sec — we track to avoid hitting it
    RATE_LIMIT = 100

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self._request_times: List[float] = []

    # ─── Rate Limiting ──────────────────────────────────────────

    def _rate_limit_wait(self):
        """Enforce 100 req/sec rate limit"""
        now = time.time()
        # Remove timestamps older than 1 second
        self._request_times = [t for t in self._request_times if now - t < 1.0]
        if len(self._request_times) >= self.RATE_LIMIT:
            sleep_time = 1.0 - (now - self._request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self._request_times.append(time.time())

    # ─── Authentication ─────────────────────────────────────────

    def _get_timestamp(self) -> int:
        """Get server timestamp for signing"""
        resp = self.session.get(f"{self.BASE_URL}/api/v3/servertime")
        return int(resp.text)

    def _sign(self, method: str, path: str, timestamp: int, body: dict = None) -> str:
        """
        Create HMAC-SHA256 signature for Bitkub API v3.

        Payload format: {timestamp}{method}{path}{json_body}
        Then HMAC-SHA256 with api_secret as key → hex digest.
        """
        body_str = json.dumps(body) if body is not None else ""
        payload = f"{timestamp}{method}{path}{body_str}"
        sig = hmac.new(
            self.api_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return sig

    def _private_request(self, path: str, body: dict = None) -> Dict:
        """Make authenticated request to Bitkub API v3"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret required for private endpoints")

        self._rate_limit_wait()

        ts = self._get_timestamp()
        method = "POST"
        body = body or {}

        sig = self._sign(method, path, ts, body)

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-BTK-APIKEY": self.api_key,
            "X-BTK-TIMESTAMP": str(ts),
            "X-BTK-SIGN": sig,
        }

        resp = self.session.post(
            f"{self.BASE_URL}{path}",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("error") != 0:
            error_code = data.get("error")
            raise BitkubAPIError(error_code, self._error_message(error_code))

        return data.get("result", data)

    def _public_request(self, path: str, params: dict = None) -> Any:
        """Make public (no auth) request"""
        self._rate_limit_wait()
        resp = self.session.get(f"{self.BASE_URL}{path}", params=params)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("error") not in (None, 0):
            error_code = data.get("error")
            raise BitkubAPIError(error_code, self._error_message(error_code))
        return data

    # ─── Public Endpoints ───────────────────────────────────────

    def symbols(self) -> List[Dict]:
        """List all available symbols"""
        data = self._public_request("/api/v3/market/symbols")
        if isinstance(data, dict):
            return data.get("result", [])
        return data

    def ticker(self, sym: str = None) -> Dict:
        """
        Get ticker(s). Returns dict keyed by symbol.
        Normalizes v3 list response into {symbol: {last, percent_change, ...}}.
        """
        params = {"sym": sym} if sym else None
        data = self._public_request("/api/v3/market/ticker", params)
        # v3 returns a list of dicts with 'symbol' field — normalize to dict
        if isinstance(data, list):
            return {item["symbol"]: item for item in data if "symbol" in item}
        return data

    def trades(self, sym: str, limit: int = 100) -> List:
        """Recent trades: [[timestamp, rate, amount, side], ...]"""
        return self._public_request(
            "/api/v3/market/trades",
            params={"sym": sym, "lmt": limit},
        )

    def depth(self, sym: str, limit: int = 20) -> Dict:
        """
        Order book depth.
        Returns: {"asks": [[price, volume], ...], "bids": [[price, volume], ...]}
        """
        return self._public_request(
            "/api/v3/market/depth",
            params={"sym": sym, "lmt": limit},
        )

    def tradingview_history(self, sym: str, resolution: str = "60",
                           from_ts: int = None, to_ts: int = None) -> Dict:
        """
        OHLCV candle data (TradingView format).
        resolution: 1, 5, 15, 60, 240, 1D
        Returns: {c: [...], h: [...], l: [...], o: [...], v: [...], t: [...], s: "ok"}
        """
        if to_ts is None:
            to_ts = int(time.time())
        if from_ts is None:
            from_ts = to_ts - (30 * 24 * 3600)  # 30 days default

        return self._public_request(
            "/tradingview/history",
            params={
                "symbol": sym,
                "resolution": resolution,
                "from": from_ts,
                "to": to_ts,
            },
        )

    # ─── Private Endpoints ──────────────────────────────────────

    def balances(self) -> Dict:
        """Get wallet balances. Returns: {"THB": {available, reserved}, "BTC": {...}, ...}"""
        return self._private_request("/api/v3/market/balances")

    def place_bid(self, sym: str, amt: float, rat: float = 0, typ: str = "market") -> Dict:
        """
        Place a buy order.
        sym: e.g. "THB_BTC"
        amt: amount in THB (for market) or quantity (for limit)
        rat: rate/price (0 for market order)
        typ: "market" or "limit"
        """
        return self._private_request("/api/v3/market/place-bid", {
            "sym": sym, "amt": amt, "rat": rat, "typ": typ,
        })

    def place_ask(self, sym: str, amt: float, rat: float = 0, typ: str = "market") -> Dict:
        """
        Place a sell order.
        amt: amount in crypto units
        rat: rate/price (0 for market)
        typ: "market" or "limit"
        """
        return self._private_request("/api/v3/market/place-ask", {
            "sym": sym, "amt": amt, "rat": rat, "typ": typ,
        })

    def cancel_order(self, sym: str, order_id: str, side: str) -> Dict:
        """Cancel an open order. side: "buy" or "sell" """
        return self._private_request("/api/v3/market/cancel-order", {
            "sym": sym, "id": order_id, "sd": side,
        })

    def order_info(self, sym: str, order_id: str, side: str) -> Dict:
        """Get order status. side: "buy" or "sell" """
        return self._private_request("/api/v3/market/order-info", {
            "sym": sym, "id": order_id, "sd": side,
        })

    def my_open_orders(self, sym: str) -> List:
        """List open orders for a symbol"""
        return self._private_request("/api/v3/market/my-open-orders", {"sym": sym})

    # ─── Helpers ────────────────────────────────────────────────

    @staticmethod
    def to_symbol(coin: str) -> str:
        """Convert user-friendly coin name to Bitkub symbol. BTC → BTC_THB"""
        coin = coin.upper().strip()
        if coin.endswith("_THB"):
            return coin
        return f"{coin}_THB"

    @staticmethod
    def from_symbol(sym: str) -> str:
        """BTC_THB → BTC"""
        return sym.replace("_THB", "")

    @staticmethod
    def _error_message(code: int) -> str:
        """Map Bitkub error codes to messages"""
        errors = {
            0: "No error",
            1: "Invalid JSON payload",
            2: "Missing X-BTK-APIKEY",
            3: "Invalid API key",
            4: "API pending for activation",
            5: "IP not allowed",
            6: "Missing/invalid signature",
            7: "Missing timestamp",
            8: "Invalid timestamp",
            9: "Invalid user",
            10: "Invalid parameter",
            11: "Invalid symbol",
            12: "Invalid amount",
            13: "Invalid rate",
            14: "Improper rate",
            15: "Amount too low",
            16: "Failed to get balance",
            17: "Wallet is empty",
            18: "Insufficient balance",
            19: "Failed to insert order",
            20: "Failed to deduct balance",
            21: "Invalid order for cancellation",
            22: "Invalid side",
            23: "Failed to update order",
            30: "Limit exceeds",
            40: "Pending withdrawal exists",
            41: "Invalid currency for withdrawal",
            42: "Address is not whitelisted",
            43: "Failed to deduct crypto",
            44: "Failed to create withdrawal record",
            90: "Server error (contact support)",
        }
        return errors.get(code, f"Unknown error code: {code}")


class BitkubAPIError(Exception):
    """Bitkub API error with error code"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Bitkub API Error {code}: {message}")
