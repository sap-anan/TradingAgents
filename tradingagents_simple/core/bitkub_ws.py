"""
Bitkub WebSocket client — real-time ticker feed.
Runs in a daemon thread, updates a shared dict.

Usage:
    ws = BitkubWebSocket(coins=["BTC", "ETH"])
    ws.start()
    prices = ws.get_prices()  # {"BTC": {"last": ..., ...}, ...}
    ws.stop()
"""
import json
import time
import threading
import websocket
from typing import Dict, List, Optional


class BitkubWebSocket:
    WS_BASE = "wss://api.bitkub.com/websocket-api"
    MAX_BACKOFF = 30

    def __init__(self, coins: List[str]):
        if not coins:
            raise ValueError("coins list cannot be empty")
        self.coins = [c.upper() for c in coins]
        self._prices: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._retry_count = 0
        self.status = "disconnected"

    def _build_url(self) -> str:
        streams = ",".join(f"market.ticker.thb_{c.lower()}" for c in self.coins)
        return f"{self.WS_BASE}/{streams}"

    def _on_message(self, ws, message: str):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        stream = data.get("stream", "")
        if "market.ticker.thb_" not in stream:
            return
        coin = stream.split("thb_")[1].upper()
        if not coin or coin not in self.coins:
            return
        with self._lock:
            self._prices[coin] = {
                "last": data.get("last", 0),
                "bid": data.get("highestBid", 0),
                "ask": data.get("lowestAsk", 0),
                "change_pct": data.get("percentChange", 0),
                "volume": data.get("baseVolume", 0),
                "high_24h": data.get("high24hr", 0),
                "low_24h": data.get("low24hr", 0),
                "updated": time.time(),
            }

    def _on_open(self, ws):
        with self._lock:
            self.status = "connected"
        self._retry_count = 0

    def _on_close(self, ws, close_status, close_msg):
        with self._lock:
            self.status = "disconnected"
        if self._running:
            self._reconnect()

    def _on_error(self, ws, error):
        with self._lock:
            self.status = "reconnecting"

    def _backoff_delay(self, attempt: int) -> int:
        return min(2 ** attempt, self.MAX_BACKOFF)

    def _reconnect(self):
        with self._lock:
            self.status = "reconnecting"
        delay = self._backoff_delay(self._retry_count)
        self._retry_count += 1
        time.sleep(delay)
        if self._running:
            self._connect()

    def _connect(self):
        url = self._build_url()
        self._ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_open=self._on_open,
            on_close=self._on_close,
            on_error=self._on_error,
        )
        self._ws.run_forever()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._ws:
            self._ws.close()

    def get_prices(self) -> Dict[str, dict]:
        with self._lock:
            return dict(self._prices)
