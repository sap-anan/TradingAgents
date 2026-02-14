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
