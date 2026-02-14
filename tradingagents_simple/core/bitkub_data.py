"""
Bitkub Data Fetcher - Crypto market data in the SAME format as DataFetcher
Plugs into the existing agent pipeline — all analysts work unchanged.

Uses Bitkub's TradingView history endpoint for OHLCV candles,
and ticker endpoint for real-time price.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from core.bitkub_client import BitkubClient


class BitkubDataFetcher:
    """
    Fetches crypto data from Bitkub in the same format as DataFetcher.
    Drop-in replacement: agents don't know they're analyzing crypto.

    Usage:
        fetcher = BitkubDataFetcher(BITKUB_DATA_CONFIG)
        data = fetcher.fetch_stock_data("BTC")  # same method name!
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.lookback_days = config.get("lookback_days", 30)
        self.resolution = config.get("candle_resolution", "60")  # 1h default
        self.client = BitkubClient()  # Public endpoints, no auth needed

    def fetch_stock_data(self, ticker: str, date: str = None) -> Dict[str, Any]:
        """
        Fetch crypto data in the SAME format as DataFetcher.fetch_stock_data().
        ticker: coin name like "BTC", "ETH", "ADA" (auto-maps to THB_BTC etc.)
        """
        sym = BitkubClient.to_symbol(ticker)
        coin = BitkubClient.from_symbol(sym)

        # 1. Get current ticker data
        ticker_data = self.client.ticker(sym=sym)
        # ticker returns {sym: {last, high24hr, low24hr, ...}} or just the inner dict
        if sym in ticker_data:
            t = ticker_data[sym]
        else:
            # Might be keyed differently, try first value
            t = next(iter(ticker_data.values())) if ticker_data else {}

        current_price = float(t.get("last", 0))

        # 2. Get OHLCV candle history from TradingView endpoint
        to_ts = int(time.time())
        from_ts = to_ts - (self.lookback_days * 24 * 3600)
        candles = self.client.tradingview_history(
            sym=sym,
            resolution=self.resolution,
            from_ts=from_ts,
            to_ts=to_ts,
        )

        closes = [float(c) for c in candles.get("c", [])]
        opens = [float(o) for o in candles.get("o", [])]
        highs = [float(h) for h in candles.get("h", [])]
        lows = [float(l) for l in candles.get("l", [])]
        volumes = [float(v) for v in candles.get("v", [])]
        timestamps = [int(ts) for ts in candles.get("t", [])]

        if not closes:
            raise ValueError(f"No candle data for {sym}")

        # Build daily OHLCV by aggregating hourly candles
        daily = self._aggregate_daily(timestamps, opens, highs, lows, closes, volumes)

        # Use daily closes for indicator calculation
        daily_closes = [d["close"] for d in daily]
        daily_volumes = [d["volume"] for d in daily]
        daily_dates = [d["date"] for d in daily]

        # Latest candle as "today's" OHLCV
        data = {
            "ticker": coin,
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "current_price": current_price,
            "prices": {
                "open": daily[-1]["open"] if daily else current_price,
                "high": daily[-1]["high"] if daily else current_price,
                "low": daily[-1]["low"] if daily else current_price,
                "close": current_price,
            },
            "volume": daily[-1]["volume"] if daily else 0,
            "history": {
                "prices": daily_closes,
                "volumes": daily_volumes,
                "dates": daily_dates,
            },
            "indicators": self._calculate_indicators(daily_closes, daily_volumes),
            "info": {
                "name": f"{coin}/THB (Bitkub)",
                "sector": "Cryptocurrency",
                "market_cap": 0,  # Not available from Bitkub
            },
            "currency": "฿",
        }

        return data

    def _aggregate_daily(self, timestamps: List[int], opens: List[float],
                         highs: List[float], lows: List[float],
                         closes: List[float], volumes: List[float]) -> List[Dict]:
        """Aggregate hourly candles into daily OHLCV"""
        if not timestamps:
            return []

        days: Dict[str, Dict] = {}
        for i, ts in enumerate(timestamps):
            day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            if day not in days:
                days[day] = {
                    "date": day,
                    "open": opens[i],
                    "high": highs[i],
                    "low": lows[i],
                    "close": closes[i],
                    "volume": volumes[i],
                }
            else:
                d = days[day]
                d["high"] = max(d["high"], highs[i])
                d["low"] = min(d["low"], lows[i])
                d["close"] = closes[i]  # Last candle's close
                d["volume"] += volumes[i]

        return sorted(days.values(), key=lambda x: x["date"])

    def _calculate_indicators(self, closes: List[float],
                              volumes: List[float]) -> Dict[str, Optional[float]]:
        """Calculate technical indicators from daily closes — same as DataFetcher"""
        if not closes or len(closes) < 2:
            return {
                "sma_20": None, "sma_50": None, "rsi": None,
                "price_change_pct": 0, "volatility": None,
            }

        # SMA
        sma_20 = sum(closes[-20:]) / min(len(closes), 20) if len(closes) >= 20 else None
        sma_50 = sum(closes[-50:]) / min(len(closes), 50) if len(closes) >= 50 else None

        # RSI (14-period)
        rsi = self._calc_rsi(closes, period=14)

        # Price change %
        price_change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100

        # Daily volatility %
        returns = [(closes[i] - closes[i-1]) / closes[i-1] * 100
                   for i in range(1, len(closes))]
        volatility = (sum(r**2 for r in returns) / len(returns)) ** 0.5 if returns else None

        return {
            "sma_20": round(sma_20, 2) if sma_20 else None,
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "rsi": round(rsi, 2) if rsi else None,
            "price_change_pct": round(price_change_pct, 2),
            "volatility": round(volatility, 2) if volatility else None,
        }

    @staticmethod
    def _calc_rsi(closes: List[float], period: int = 14) -> Optional[float]:
        """RSI calculation matching DataFetcher's approach"""
        if len(closes) < period + 1:
            return None

        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Smoothed RSI (Wilder's method)
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def list_symbols(self) -> List[str]:
        """List all tradeable coins on Bitkub"""
        ticker_data = self.client.ticker()
        return sorted(ticker_data.keys()) if isinstance(ticker_data, dict) else []
