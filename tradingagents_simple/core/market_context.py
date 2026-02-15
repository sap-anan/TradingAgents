"""
Market Context — Aggregates watcher snapshots into daily context for AI agents.
Reads JSONL snapshots → computes OHLCV, regime, volatility, events → context string.

Usage:
    from core.market_context import MarketContext
    ctx = MarketContext.load_today()      # dict with full daily context
    text = MarketContext.context_string()  # human-readable for agent prompts
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

from config import WATCHER_CONFIG

DATA_DIR = WATCHER_CONFIG["data_dir"]
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")
CONTEXT_DIR = os.path.join(DATA_DIR, "context")
EVENT_DIR = os.path.join(DATA_DIR, "events")


class MarketContext:
    """Aggregates watcher data into actionable context for trading agents."""

    @staticmethod
    def load_today(date: str = None) -> Optional[Dict]:
        """
        Load or generate today's market context.
        First checks for cached context file, then generates from snapshots.
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        cache_path = os.path.join(CONTEXT_DIR, f"{date}.json")

        # Try cached context
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                return json.load(f)

        # Generate from snapshots
        snapshot_file = os.path.join(SNAPSHOT_DIR, f"{date}.jsonl")
        if not os.path.exists(snapshot_file):
            return None

        snapshots = []
        with open(snapshot_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    snapshots.append(json.loads(line))

        if not snapshots:
            return None

        ctx = MarketContext._build_context(date, snapshots)

        # Load events
        event_file = os.path.join(EVENT_DIR, f"{date}.jsonl")
        if os.path.exists(event_file):
            events = []
            with open(event_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
            # Attach events to their coins
            for ev in events:
                coin = ev.get("coin")
                if coin and coin in ctx["coins"]:
                    ctx["coins"][coin].setdefault("events", []).append(ev)

        # Cache it
        os.makedirs(CONTEXT_DIR, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(ctx, f, indent=2, default=str)

        return ctx

    @staticmethod
    def _build_context(date: str, snapshots: List[Dict]) -> Dict:
        """Build context dict from raw snapshots."""
        # Collect all coins seen
        all_coins = set()
        for snap in snapshots:
            all_coins.update(snap.get("coins", {}).keys())

        coins_ctx = {}
        for coin in sorted(all_coins):
            prices = []
            volumes = []
            timestamps = []

            for snap in snapshots:
                coin_data = snap.get("coins", {}).get(coin)
                if not coin_data:
                    continue
                prices.append(coin_data["price"])
                volumes.append(coin_data.get("vol_24h", 0))
                timestamps.append(snap["ts"])

            if not prices:
                continue

            open_p = prices[0]
            close_p = prices[-1]
            high_p = max(prices)
            low_p = min(prices)
            change_pct = ((close_p - open_p) / open_p * 100) if open_p else 0

            # Volatility: std of returns as % of mean price
            if len(prices) >= 2:
                returns = [abs(prices[i] - prices[i-1]) / prices[i-1] * 100
                           for i in range(1, len(prices))]
                avg_return = sum(returns) / len(returns) if returns else 0
                volatility = "HIGH" if avg_return > 0.5 else "MEDIUM" if avg_return > 0.2 else "LOW"
            else:
                volatility = "UNKNOWN"

            # Regime detection
            regime = MarketContext._detect_regime(prices)

            # Summary text
            summary = MarketContext._make_summary(coin, open_p, close_p, high_p, low_p,
                                                   change_pct, volatility, regime, len(snapshots))

            coins_ctx[coin] = {
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "change_pct": round(change_pct, 2),
                "regime": regime,
                "volatility": volatility,
                "tick_count": len(prices),
                "summary": summary,
            }

        # Overall market sentiment
        sentiments = []
        for c in coins_ctx.values():
            sentiments.append(c["change_pct"])
        avg_change = sum(sentiments) / len(sentiments) if sentiments else 0

        if avg_change > 3:
            market_sentiment = "BULLISH"
        elif avg_change > 1:
            market_sentiment = "BULLISH_CAUTIOUS"
        elif avg_change > -1:
            market_sentiment = "NEUTRAL"
        elif avg_change > -3:
            market_sentiment = "BEARISH_CAUTIOUS"
        else:
            market_sentiment = "BEARISH"

        return {
            "date": date,
            "coins": coins_ctx,
            "market_sentiment": market_sentiment,
            "snapshot_count": len(snapshots),
            "generated_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _detect_regime(prices: List[float]) -> str:
        """Simple regime detection from price series."""
        if len(prices) < 3:
            return "UNKNOWN"

        # Split into thirds and compare means
        n = len(prices)
        third = n // 3
        if third == 0:
            return "SIDEWAYS"

        first_avg = sum(prices[:third]) / third
        last_avg = sum(prices[-third:]) / third
        pct_change = (last_avg - first_avg) / first_avg * 100

        if pct_change > 2:
            return "UPTREND"
        elif pct_change < -2:
            return "DOWNTREND"
        else:
            return "SIDEWAYS"

    @staticmethod
    def _make_summary(coin: str, open_p: float, close_p: float, high_p: float,
                      low_p: float, change_pct: float, volatility: str,
                      regime: str, tick_count: int) -> str:
        """Generate human-readable summary for one coin."""
        direction = "up" if change_pct >= 0 else "down"
        parts = [f"{coin} {direction} {abs(change_pct):.1f}% today"]
        parts.append(f"(฿{open_p:,.0f} → ฿{close_p:,.0f})")

        spread_pct = (high_p - low_p) / low_p * 100 if low_p else 0
        if spread_pct > 5:
            parts.append(f"with wide range ฿{low_p:,.0f}–฿{high_p:,.0f} ({spread_pct:.1f}% spread)")

        if volatility == "HIGH":
            parts.append("— high volatility")

        parts.append(f"[{regime.lower()}, {tick_count} ticks]")
        return " ".join(parts)

    @staticmethod
    def context_string(date: str = None) -> str:
        """
        Generate a context string suitable for injecting into agent prompts.
        Returns empty string if no data available.
        """
        ctx = MarketContext.load_today(date)
        if not ctx:
            return ""

        lines = [f"=== Market Context ({ctx['date']}) ==="]
        lines.append(f"Sentiment: {ctx['market_sentiment']} | Ticks: {ctx['snapshot_count']}")

        for coin, data in ctx.get("coins", {}).items():
            lines.append(f"\n{coin}: {data['summary']}")
            events = data.get("events", [])
            for ev in events[:3]:  # Max 3 events per coin
                lines.append(f"  ⚡ {ev.get('time', '?')}: {ev.get('description', ev.get('type', ''))}")

        return "\n".join(lines)

    @staticmethod
    def invalidate_cache(date: str = None):
        """Remove cached context to force regeneration."""
        date = date or datetime.now().strftime("%Y-%m-%d")
        cache_path = os.path.join(CONTEXT_DIR, f"{date}.json")
        if os.path.exists(cache_path):
            os.remove(cache_path)
