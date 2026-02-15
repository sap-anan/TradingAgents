# Dashboard Real-Time WebSocket + Analytics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time Bitkub WebSocket price feeds and RSI/volume analytics to the Streamlit dashboard.

**Architecture:** Background daemon thread connects to Bitkub WebSocket ticker streams, updates `st.session_state["live_prices"]`. `streamlit-autorefresh` triggers UI re-render every 3s. RSI(14) computed from existing 5-min snapshots. Volume bars added to candlestick chart.

**Tech Stack:** `websocket-client`, `streamlit-autorefresh`, Plotly, existing Streamlit dashboard

---

### Task 1: Install Dependencies

**Files:**
- Modify: `tradingagents_simple/.venv/` (pip install)

**Step 1: Install packages**

Run:
```bash
cd /home/sap-anan/projects/TradingAgents/tradingagents_simple
source .venv/bin/activate
pip install websocket-client streamlit-autorefresh
```

Expected: Successfully installed

**Step 2: Commit**

```bash
git add -A
git commit -m "chore: add websocket-client and streamlit-autorefresh deps"
```

---

### Task 2: BitkubWebSocket Class

**Files:**
- Create: `tradingagents_simple/core/bitkub_ws.py`
- Create: `tradingagents_simple/tests/test_bitkub_ws.py`

**Step 1: Write the failing test**

```python
# tests/test_bitkub_ws.py
import pytest
import json
import time
from unittest.mock import patch, MagicMock
from core.bitkub_ws import BitkubWebSocket


def test_parse_ticker_message():
    """Verify ticker message is parsed into our standard format."""
    ws = BitkubWebSocket(coins=["BTC"])
    raw = json.dumps({
        "stream": "market.ticker.thb_btc",
        "id": 1,
        "last": 2850000.0,
        "lowestAsk": 2850100.0,
        "highestBid": 2849900.0,
        "change": 34000.0,
        "percentChange": 1.21,
        "baseVolume": 450.5,
        "quoteVolume": 1282500000.0,
        "high24hr": 2870000.0,
        "low24hr": 2820000.0,
    })
    ws._on_message(None, raw)
    prices = ws.get_prices()
    assert "BTC" in prices
    assert prices["BTC"]["last"] == 2850000.0
    assert prices["BTC"]["bid"] == 2849900.0
    assert prices["BTC"]["ask"] == 2850100.0
    assert prices["BTC"]["change_pct"] == 1.21
    assert prices["BTC"]["volume"] == 450.5
    assert prices["BTC"]["high_24h"] == 2870000.0
    assert prices["BTC"]["low_24h"] == 2820000.0


def test_build_stream_url():
    """Verify WebSocket URL is built correctly for multiple coins."""
    ws = BitkubWebSocket(coins=["BTC", "ETH", "XRP"])
    url = ws._build_url()
    assert "market.ticker.thb_btc" in url
    assert "market.ticker.thb_eth" in url
    assert "market.ticker.thb_xrp" in url
    assert url.startswith("wss://api.bitkub.com/websocket-api/")


def test_reconnect_backoff():
    """Verify exponential backoff capped at 30s."""
    ws = BitkubWebSocket(coins=["BTC"])
    assert ws._backoff_delay(0) == 1
    assert ws._backoff_delay(1) == 2
    assert ws._backoff_delay(2) == 4
    assert ws._backoff_delay(10) == 30  # capped
```

**Step 2: Run test to verify it fails**

Run: `cd /home/sap-anan/projects/TradingAgents/tradingagents_simple && source .venv/bin/activate && python -m pytest tests/test_bitkub_ws.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.bitkub_ws'`

**Step 3: Write minimal implementation**

```python
# core/bitkub_ws.py
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
        self.coins = [c.upper() for c in coins]
        self._prices: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._retry_count = 0
        self.status = "disconnected"  # disconnected | connected | reconnecting

    def _build_url(self) -> str:
        streams = ",".join(f"market.ticker.thb_{c.lower()}" for c in self.coins)
        return f"{self.WS_BASE}/{streams}"

    def _on_message(self, ws, message: str):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        stream = data.get("stream", "")
        # Extract coin from "market.ticker.thb_btc" → "BTC"
        if "market.ticker.thb_" not in stream:
            return
        coin = stream.split("thb_")[1].upper()

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
        self.status = "connected"
        self._retry_count = 0

    def _on_close(self, ws, close_status, close_msg):
        self.status = "disconnected"
        if self._running:
            self._reconnect()

    def _on_error(self, ws, error):
        self.status = "reconnecting"

    def _backoff_delay(self, attempt: int) -> int:
        return min(2 ** attempt, self.MAX_BACKOFF)

    def _reconnect(self):
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
        """Start WebSocket in daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop WebSocket."""
        self._running = False
        if self._ws:
            self._ws.close()

    def get_prices(self) -> Dict[str, dict]:
        """Get current prices (thread-safe copy)."""
        with self._lock:
            return dict(self._prices)
```

**Step 4: Run test to verify it passes**

Run: `cd /home/sap-anan/projects/TradingAgents/tradingagents_simple && source .venv/bin/activate && python -m pytest tests/test_bitkub_ws.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add core/bitkub_ws.py tests/test_bitkub_ws.py
git commit -m "feat: BitkubWebSocket client with auto-reconnect"
```

---

### Task 3: RSI Indicator

**Files:**
- Create: `tradingagents_simple/core/indicators.py`
- Create: `tradingagents_simple/tests/test_indicators.py`

**Step 1: Write the failing test**

```python
# tests/test_indicators.py
import pytest
from core.indicators import rsi


def test_rsi_known_values():
    """RSI of flat prices should be 50 (no gains or losses)."""
    prices = [100.0] * 20
    result = rsi(prices, period=14)
    assert len(result) > 0
    assert result[-1] == pytest.approx(50.0, abs=0.1)


def test_rsi_all_up():
    """RSI of strictly increasing prices should be near 100."""
    prices = [float(i) for i in range(1, 30)]
    result = rsi(prices, period=14)
    assert result[-1] > 90


def test_rsi_all_down():
    """RSI of strictly decreasing prices should be near 0."""
    prices = [float(30 - i) for i in range(30)]
    result = rsi(prices, period=14)
    assert result[-1] < 10


def test_rsi_insufficient_data():
    """RSI with fewer than period+1 prices returns empty list."""
    prices = [100.0] * 10
    result = rsi(prices, period=14)
    assert result == []
```

**Step 2: Run test to verify it fails**

Run: `cd /home/sap-anan/projects/TradingAgents/tradingagents_simple && source .venv/bin/activate && python -m pytest tests/test_indicators.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# core/indicators.py
"""Technical indicators computed from price series."""
from typing import List


def rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    Relative Strength Index (Wilder's smoothing).

    Args:
        prices: List of closing prices (oldest first).
        period: RSI lookback period (default 14).

    Returns:
        List of RSI values, length = len(prices) - period.
        Empty list if insufficient data.
    """
    if len(prices) < period + 1:
        return []

    deltas = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]

    # Seed: simple average of first `period` deltas
    gains = [max(d, 0) for d in deltas[:period]]
    losses = [abs(min(d, 0)) for d in deltas[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    results = []
    # First RSI value
    if avg_loss == 0:
        results.append(100.0 if avg_gain > 0 else 50.0)
    else:
        rs = avg_gain / avg_loss
        results.append(100.0 - (100.0 / (1.0 + rs)))

    # Subsequent values: Wilder's smoothing
    for i in range(period, len(deltas)):
        d = deltas[i]
        gain = max(d, 0)
        loss = abs(min(d, 0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            results.append(100.0 if avg_gain > 0 else 50.0)
        else:
            rs = avg_gain / avg_loss
            results.append(100.0 - (100.0 / (1.0 + rs)))

    return results
```

**Step 4: Run test to verify it passes**

Run: `cd /home/sap-anan/projects/TradingAgents/tradingagents_simple && source .venv/bin/activate && python -m pytest tests/test_indicators.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add core/indicators.py tests/test_indicators.py
git commit -m "feat: RSI(14) indicator with Wilder's smoothing"
```

---

### Task 4: Dashboard — Live Ticker Cards with WebSocket

**Files:**
- Modify: `tradingagents_simple/dashboard.py` (Market Watcher tab, lines 438-520)

**Step 1: Add autorefresh and WebSocket initialization at top of dashboard.py**

After the existing imports (line 14), add:

```python
from streamlit_autorefresh import st_autorefresh
from core.bitkub_ws import BitkubWebSocket
```

After `st.set_page_config(...)` (line 30), add:

```python
# Auto-refresh every 3 seconds
st_autorefresh(interval=3000, limit=None, key="live_refresh")
```

**Step 2: Initialize WebSocket in session_state**

After session state init block (line 34), add:

```python
if "bitkub_ws" not in st.session_state:
    coins = load_watchlist()  # needs import moved up
    ws = BitkubWebSocket(coins=coins)
    ws.start()
    st.session_state["bitkub_ws"] = ws
```

Note: `load_watchlist` is imported from `watcher` at line 22 — already available.

**Step 3: Replace static metric cards with live WebSocket prices**

In the Market Watcher tab (line 460), replace the `st.subheader("📊 Current Prices")` block with:

```python
        # ─── Live Ticker Cards ───
        st.subheader("📊 Live Prices")
        ws = st.session_state.get("bitkub_ws")
        live = ws.get_prices() if ws else {}
        status_icon = {"connected": "🟢", "disconnected": "🔴",
                       "reconnecting": "🟡"}.get(ws.status if ws else "", "⚪")
        st.caption(f"WebSocket: {status_icon} {ws.status if ws else 'N/A'}")

        cols = st.columns(min(len(selected_coins), 4) or 1)
        for i, coin in enumerate(selected_coins):
            # Prefer live data, fallback to last snapshot
            if coin in live:
                cd = live[coin]
                price = cd["last"]
                change = cd["change_pct"]
                extra = (f"Bid: ฿{cd['bid']:,.0f} | Ask: ฿{cd['ask']:,.0f} | "
                         f"Vol: {cd['volume']:.2f}")
            else:
                cd = last_snap.get("coins", {}).get(coin)
                if not cd:
                    continue
                price = cd["price"]
                change = cd.get("change_24h", 0)
                extra = "📡 Snapshot data"

            with cols[i % len(cols)]:
                st.metric(label=coin, value=f"฿{price:,.2f}",
                          delta=f"{change:+.2f}%")
                st.caption(extra)
```

**Step 4: Manually test**

Run: `cd /home/sap-anan/projects/TradingAgents/tradingagents_simple && source .venv/bin/activate && streamlit run dashboard.py`
Expected: Market Watcher tab shows live prices updating every 3s with 🟢 status

**Step 5: Commit**

```bash
git add dashboard.py
git commit -m "feat: live WebSocket ticker cards with auto-refresh"
```

---

### Task 5: Dashboard — Volume Bars on Candlestick Chart

**Files:**
- Modify: `tradingagents_simple/dashboard.py` (candlestick section, ~line 500)

**Step 1: Modify aggregate_to_1h_ohlc to include volume**

In `aggregate_to_1h_ohlc()` (line 92), change tick collection to also grab volume:

```python
def aggregate_to_1h_ohlc(snapshots, coin):
    """Aggregate 5-minute snapshot ticks into 1-hour OHLC candles."""
    ticks = []
    for snap in snapshots:
        cd = snap.get("coins", {}).get(coin)
        if cd:
            ticks.append((snap["ts"], cd["price"], cd.get("volume_24h", 0)))

    if len(ticks) < 2:
        return None

    buckets = {}
    for ts, price, vol in ticks:
        hour_key = ts // 3600
        buckets.setdefault(hour_key, []).append((ts, price, vol))

    if len(buckets) < 2:
        return None

    candles = []
    for hour_key in sorted(buckets):
        pts = buckets[hour_key]
        pts.sort(key=lambda x: x[0])
        prices = [p for _, p, _ in pts]
        # Volume delta: last - first snapshot volume in this hour
        vols = [v for _, _, v in pts]
        vol_delta = max(vols[-1] - vols[0], 0) if vols else 0
        candles.append({
            "ts": hour_key * 3600,
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
            "volume": vol_delta,
        })
    return candles
```

**Step 2: Add volume bars to candlestick chart**

Replace the candlestick chart rendering (line 507) with:

```python
            from plotly.subplots import make_subplots

            fig_candle = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.7, 0.3],
            )
            fig_candle.add_trace(go.Candlestick(
                x=[datetime.fromtimestamp(c["ts"]) for c in candles],
                open=[c["open"] for c in candles],
                high=[c["high"] for c in candles],
                low=[c["low"] for c in candles],
                close=[c["close"] for c in candles],
                name=coin,
            ), row=1, col=1)

            # Volume bars colored by candle direction
            colors = ["#00cc66" if c["close"] >= c["open"] else "#ff4444"
                      for c in candles]
            fig_candle.add_trace(go.Bar(
                x=[datetime.fromtimestamp(c["ts"]) for c in candles],
                y=[c["volume"] for c in candles],
                marker_color=colors, name="Volume", opacity=0.6,
            ), row=2, col=1)

            fig_candle.update_layout(
                title=f"{coin} — 1H Candles + Volume",
                xaxis_rangeslider_visible=False,
                height=500, margin=dict(t=40, b=30, l=50, r=20),
                showlegend=False,
            )
            fig_candle.update_yaxes(title_text="Price (THB)", row=1, col=1)
            fig_candle.update_yaxes(title_text="Volume", row=2, col=1)
            st.plotly_chart(fig_candle, use_container_width=True)
```

**Step 3: Manually test**

Run: `streamlit run dashboard.py`
Expected: Candlestick chart now has volume bars below, colored green/red

**Step 4: Commit**

```bash
git add dashboard.py
git commit -m "feat: volume bars on candlestick chart"
```

---

### Task 6: Dashboard — RSI Chart

**Files:**
- Modify: `tradingagents_simple/dashboard.py` (after candlestick section)

**Step 1: Add RSI subplot below candlestick**

After the candlestick chart section, add:

```python
        # ─── RSI Chart ───
        st.subheader("📉 RSI(14)")
        from core.indicators import rsi

        for coin in selected_coins:
            prices = []
            times = []
            for snap in snapshots:
                cd = snap.get("coins", {}).get(coin)
                if cd:
                    prices.append(cd["price"])
                    times.append(datetime.fromtimestamp(snap["ts"]))

            rsi_values = rsi(prices, period=14)
            if not rsi_values:
                st.caption(f"{coin}: Not enough data for RSI (need 15+ ticks)")
                continue

            # RSI timestamps align with prices[period:]
            rsi_times = times[14:]  # skip first `period` prices

            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(
                x=rsi_times, y=rsi_values,
                mode="lines", name="RSI(14)",
                line=dict(color="#8b5cf6", width=2),
            ))
            # Overbought / Oversold lines
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red",
                              annotation_text="Overbought")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green",
                              annotation_text="Oversold")
            fig_rsi.add_hline(y=50, line_dash="dot", line_color="gray")
            fig_rsi.update_layout(
                title=f"{coin} — RSI(14)",
                yaxis=dict(range=[0, 100]),
                height=250, margin=dict(t=40, b=30, l=50, r=20),
            )
            st.plotly_chart(fig_rsi, use_container_width=True)
```

**Step 2: Manually test**

Run: `streamlit run dashboard.py`
Expected: RSI chart appears below candlestick with overbought/oversold reference lines

**Step 3: Commit**

```bash
git add dashboard.py
git commit -m "feat: RSI(14) chart on Market Watcher tab"
```

---

### Task 7: Final Integration Test & Push

**Step 1: Run all tests**

Run:
```bash
cd /home/sap-anan/projects/TradingAgents/tradingagents_simple
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: All tests pass

**Step 2: Manual smoke test**

Run: `streamlit run dashboard.py`
Verify:
- [ ] Market Watcher tab loads without errors
- [ ] WebSocket status shows 🟢 Connected
- [ ] Prices update every ~3 seconds
- [ ] Candlestick chart has volume bars
- [ ] RSI chart renders with reference lines
- [ ] Other tabs (Trading Monitor, LLM Usage) still work

**Step 3: Push**

```bash
git push origin main
```
