"""
Data Fetcher - Pluggable data sources
Current: yfinance (free), Extensible: Alpha Vantage, Polygon, etc.
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any


class DataFetcher:
    """
    Pluggable data source interface
    Extension point: Add new data providers (Polygon, Alpha Vantage, etc.)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.source = config.get("source", "yfinance")
        self.lookback_days = config.get("lookback_days", 30)

    def fetch_stock_data(self, ticker: str, date: str = None) -> Dict[str, Any]:
        """
        Fetch comprehensive stock data

        Args:
            ticker: Stock symbol (e.g., "NVDA")
            date: Target date (YYYY-MM-DD), defaults to today

        Returns:
            dict with: prices, volume, indicators, metrics
        """
        if self.source == "yfinance":
            return self._fetch_yfinance(ticker, date)
        else:
            raise ValueError(f"Unknown data source: {self.source}")

    def _fetch_yfinance(self, ticker: str, date: str = None) -> Dict[str, Any]:
        """Fetch data from Yahoo Finance (free)"""

        # Date range
        if date:
            end_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            end_date = datetime.now()

        start_date = end_date - timedelta(days=self.lookback_days)

        # Fetch data
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date)

        if hist.empty:
            raise ValueError(f"No data found for {ticker}")

        # Calculate indicators
        data = {
            "ticker": ticker,
            "date": date or end_date.strftime("%Y-%m-%d"),
            "current_price": float(hist['Close'].iloc[-1]),
            "prices": {
                "open": float(hist['Open'].iloc[-1]),
                "high": float(hist['High'].iloc[-1]),
                "low": float(hist['Low'].iloc[-1]),
                "close": float(hist['Close'].iloc[-1]),
            },
            "volume": int(hist['Volume'].iloc[-1]),
            "history": {
                "prices": hist['Close'].tolist(),
                "volumes": hist['Volume'].tolist(),
                "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
            },
            "indicators": self._calculate_indicators(hist),
            "info": self._get_stock_info(stock),
        }

        return data

    def _calculate_indicators(self, hist: pd.DataFrame) -> Dict[str, float]:
        """Calculate technical indicators"""
        close = hist['Close']

        # Simple Moving Averages
        sma_20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else None
        sma_50 = close.rolling(window=50).mean().iloc[-1] if len(close) >= 50 else None

        # RSI (Relative Strength Index)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Price change
        price_change_pct = ((close.iloc[-1] - close.iloc[0]) / close.iloc[0]) * 100 if len(close) > 0 else 0

        return {
            "sma_20": float(sma_20) if sma_20 else None,
            "sma_50": float(sma_50) if sma_50 else None,
            "rsi": float(rsi.iloc[-1]) if not rsi.empty else None,
            "price_change_pct": float(price_change_pct),
            "volatility": float(close.pct_change().std() * 100) if len(close) > 1 else None,
        }

    def _get_stock_info(self, stock) -> Dict[str, Any]:
        """Get company information"""
        try:
            info = stock.info
            return {
                "name": info.get("longName", "Unknown"),
                "sector": info.get("sector", "Unknown"),
                "market_cap": info.get("marketCap", 0),
            }
        except:
            return {"name": "Unknown", "sector": "Unknown", "market_cap": 0}


# Extension point: Add new data sources
# class AlphaVantageDataFetcher(DataFetcher):
#     def fetch_stock_data(self, ticker: str, date: str = None):
#         # Your Alpha Vantage implementation
#         pass
