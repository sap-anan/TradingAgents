# Dashboard Real-Time Updates & Better Analytics

**Date:** 2026-02-14
**Status:** Approved

## Goal

Upgrade the Streamlit dashboard with real-time Bitkub WebSocket price feeds and richer analytics (volume, RSI, live ticker cards).

## Approach

**Approach 1: Streamlit + Background WebSocket Thread** — chosen for simplicity. WebSocket runs in a daemon thread, feeds `st.session_state`, dashboard auto-refreshes via `streamlit-autorefresh`.

## Section 1: Real-Time WebSocket Feed

- `BitkubWebSocket` class wraps `websocket-client` in a daemon thread
- Connects to `wss://api.bitkub.com/websocket-api/market.ticker.thb_<coin>` for all watchlist coins
- Updates shared dict `st.session_state["live_prices"]` on each message
- `streamlit-autorefresh` triggers UI re-render every 3-5 seconds
- Auto-reconnect with exponential backoff (1s → 2s → 4s → max 30s)

**Data shape:**
```python
st.session_state["live_prices"] = {
    "BTC": {
        "last": 2850000, "bid": 2849900, "ask": 2850100,
        "change_pct": 1.2, "volume": 450.5,
        "high_24h": 2870000, "low_24h": 2820000,
        "updated": 1739520000,
    },
}
```

## Section 2: Better Analytics

1. **Volume bars** — secondary y-axis on candlestick chart (from ticker `baseVolume`)
2. **RSI(14)** — calculated from existing 5-min snapshot prices, displayed as subplot below candlestick with overbought (>70) / oversold (<30) reference lines
3. **Live ticker cards** — replace static `st.metric` with WebSocket-fed live prices updating every few seconds (last, bid/ask spread, 24h change, volume, high/low)
4. **Mini sparkline** — tiny 24h price trend inside each metric card

No new API calls — RSI from snapshots, volume/spread from WebSocket.

## Section 3: Error Handling & Testing

- Connection status indicator: 🟢 Connected / 🔴 Disconnected / 🟡 Reconnecting
- Graceful fallback: if WebSocket fails, dashboard uses existing snapshot data
- Unit tests: RSI calculation (known values), mock WebSocket reconnect logic

## File Changes

| File | Change |
|------|--------|
| `core/bitkub_ws.py` | **New** — BitkubWebSocket class |
| `core/indicators.py` | **New** — RSI calculation |
| `dashboard.py` | Modified — live cards, volume bars, RSI chart, autorefresh |
| deps | Add `websocket-client`, `streamlit-autorefresh` |

## Dependencies

- `websocket-client` — WebSocket connection
- `streamlit-autorefresh` — periodic UI refresh

## Alternatives Considered

- **Approach 2:** Standalone `ws_feeder.py` service writing to file/Redis — more robust but extra process management
- **Approach 3:** Full async FastAPI + custom frontend — overkill for learning sandbox
