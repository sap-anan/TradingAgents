"""
Market Watcher — 24/7 price monitor for Bitkub
Polls ticker API every 5 minutes, logs snapshots, detects events, alerts via Telegram.

Usage:
    python watcher.py --tick              # Single poll (for cron: */5 * * * *)
    python watcher.py --daemon            # Continuous polling
    python watcher.py --status            # Show last tick, event count
    python watcher.py --summary           # Generate/show today's context summary

Cost: ฿0 — public API only, no LLM calls.
"""
import os
import sys
import json
import time
import signal
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from core.bitkub_client import BitkubClient
from config import WATCHER_CONFIG, ALERT_CONFIG

# ─── Paths ────────────────────────────────────────────────────

DATA_DIR = WATCHER_CONFIG["data_dir"]
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")
CONTEXT_DIR = os.path.join(DATA_DIR, "context")
EVENT_DIR = os.path.join(DATA_DIR, "events")

for d in [SNAPSHOT_DIR, CONTEXT_DIR, EVENT_DIR]:
    os.makedirs(d, exist_ok=True)

# Coins to watch — loaded from watchlist
WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "data", "watchlist.json")


def load_watchlist() -> List[str]:
    """Load coins from watchlist.json, fallback to defaults."""
    if os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH) as f:
            return json.load(f)
    return ["BTC", "ETH"]


# ─── Snapshot I/O ─────────────────────────────────────────────

def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def snapshot_path(date: str = None) -> str:
    return os.path.join(SNAPSHOT_DIR, f"{date or today_str()}.jsonl")


def event_path(date: str = None) -> str:
    return os.path.join(EVENT_DIR, f"{date or today_str()}.jsonl")


def context_path(date: str = None) -> str:
    return os.path.join(CONTEXT_DIR, f"{date or today_str()}.json")


def append_jsonl(path: str, record: Dict):
    with open(path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def read_jsonl(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ─── Telegram ─────────────────────────────────────────────────

def send_telegram(text: str):
    """Send alert via Telegram Bot API."""
    token = ALERT_CONFIG.get("telegram_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = ALERT_CONFIG.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass


# ─── Core: Poll ───────────────────────────────────────────────

def poll_ticker(client: BitkubClient, coins: List[str]) -> Dict:
    """
    Fetch current prices for watched coins.
    Returns snapshot dict: {ts, coins: {BTC: {price, vol_24h, change_24h}, ...}}
    """
    ticker_data = client.ticker()
    now_ts = int(time.time())
    snapshot = {"ts": now_ts, "coins": {}}

    for coin in coins:
        sym = BitkubClient.to_symbol(coin)
        info = ticker_data.get(sym, {})
        if not info:
            continue
        snapshot["coins"][coin] = {
            "price": float(info.get("last", 0)),
            "vol_24h": float(info.get("baseVolume", 0)),
            "change_24h": float(info.get("percentChange", 0)),
            "high_24h": float(info.get("high24hr", 0)),
            "low_24h": float(info.get("low24hr", 0)),
        }

    return snapshot


# ─── Core: Event Detection ────────────────────────────────────

def detect_events(current: Dict, history: List[Dict], config: Dict) -> List[Dict]:
    """
    Analyze current snapshot against recent history to detect significant events.
    Returns list of event dicts: [{time, coin, type, magnitude, description}, ...]
    """
    events = []
    now_ts = current["ts"]
    now_str = datetime.fromtimestamp(now_ts).strftime("%H:%M")
    threshold_1h = config.get("price_alert_1h_pct", 3.0)
    threshold_4h = config.get("price_alert_4h_pct", 5.0)
    vol_mult = config.get("volume_spike_multiplier", 2.0)

    # Recent events for dedup — skip if same coin+type fired in last 30 min
    recent_events = read_jsonl(event_path())
    recent_set = set()
    for ev in recent_events:
        # Parse event time today to timestamp for comparison
        ev_key = f"{ev.get('coin')}:{ev.get('type')}"
        recent_set.add(ev_key)

    def _already_fired(coin: str, etype: str) -> bool:
        """Simple dedup: skip if same event type fired for this coin in last 6 ticks (~30 min)."""
        key = f"{coin}:{etype}"
        cutoff = now_ts - 1800  # 30 min
        for ev in reversed(recent_events):
            # Check recent event file entries
            if ev.get("coin") == coin and ev.get("type") == etype:
                # Approximate: if event is from today and recent
                try:
                    ev_dt = datetime.strptime(f"{today_str()} {ev['time']}", "%Y-%m-%d %H:%M")
                    if ev_dt.timestamp() > cutoff:
                        return True
                except (KeyError, ValueError):
                    pass
        return False

    for coin, coin_data in current.get("coins", {}).items():
        price = coin_data["price"]
        if price <= 0:
            continue

        # ── Gather historical prices for this coin ──
        def _price_at_lookback(seconds: int) -> Optional[float]:
            """Find price closest to N seconds ago."""
            target_ts = now_ts - seconds
            best = None
            best_diff = float("inf")
            for snap in history:
                diff = abs(snap["ts"] - target_ts)
                if diff < best_diff and coin in snap.get("coins", {}):
                    best_diff = diff
                    best = snap["coins"][coin]["price"]
            # Only use if within 2 tick tolerance (~10 min)
            return best if best_diff < 660 else None

        # ── Price alerts: 1h window ──
        price_1h = _price_at_lookback(3600)
        if price_1h and price_1h > 0:
            pct_1h = (price - price_1h) / price_1h * 100
            if pct_1h <= -threshold_1h and not _already_fired(coin, "PRICE_DROP_1H"):
                events.append({
                    "time": now_str, "coin": coin, "type": "PRICE_DROP_1H",
                    "magnitude": round(pct_1h, 2),
                    "description": f"{coin} dropped {abs(pct_1h):.1f}% in the last hour "
                                   f"(฿{price_1h:,.0f} → ฿{price:,.0f})",
                })
            elif pct_1h >= threshold_1h and not _already_fired(coin, "PRICE_SPIKE_1H"):
                events.append({
                    "time": now_str, "coin": coin, "type": "PRICE_SPIKE_1H",
                    "magnitude": round(pct_1h, 2),
                    "description": f"{coin} rose {pct_1h:.1f}% in the last hour "
                                   f"(฿{price_1h:,.0f} → ฿{price:,.0f})",
                })

        # ── Price alerts: 4h window ──
        price_4h = _price_at_lookback(14400)
        if price_4h and price_4h > 0:
            pct_4h = (price - price_4h) / price_4h * 100
            if pct_4h <= -threshold_4h and not _already_fired(coin, "PRICE_DROP_4H"):
                events.append({
                    "time": now_str, "coin": coin, "type": "PRICE_DROP_4H",
                    "magnitude": round(pct_4h, 2),
                    "description": f"{coin} dropped {abs(pct_4h):.1f}% in the last 4 hours "
                                   f"(฿{price_4h:,.0f} → ฿{price:,.0f})",
                })
            elif pct_4h >= threshold_4h and not _already_fired(coin, "PRICE_SPIKE_4H"):
                events.append({
                    "time": now_str, "coin": coin, "type": "PRICE_SPIKE_4H",
                    "magnitude": round(pct_4h, 2),
                    "description": f"{coin} rose {pct_4h:.1f}% in the last 4 hours "
                                   f"(฿{price_4h:,.0f} → ฿{price:,.0f})",
                })

        # ── Volume spike: current vs rolling average of last 12 ticks ──
        vol_history = []
        for snap in history[-13:-1]:  # Last 12 ticks excluding current
            cd = snap.get("coins", {}).get(coin)
            if cd:
                vol_history.append(cd.get("vol_24h", 0))
        if vol_history:
            avg_vol = sum(vol_history) / len(vol_history)
            cur_vol = coin_data.get("vol_24h", 0)
            if avg_vol > 0 and cur_vol > avg_vol * vol_mult:
                if not _already_fired(coin, "VOLUME_SPIKE"):
                    ratio = cur_vol / avg_vol
                    events.append({
                        "time": now_str, "coin": coin, "type": "VOLUME_SPIKE",
                        "magnitude": round(ratio, 2),
                        "description": f"{coin} volume spike {ratio:.1f}x above recent average",
                    })

        # ── New 24h high/low ──
        high_24h = coin_data.get("high_24h", 0)
        low_24h = coin_data.get("low_24h", 0)
        if high_24h > 0 and price >= high_24h * 0.999:  # Within 0.1% of high
            if not _already_fired(coin, "NEW_HIGH_24H"):
                events.append({
                    "time": now_str, "coin": coin, "type": "NEW_HIGH_24H",
                    "magnitude": round(coin_data.get("change_24h", 0), 2),
                    "description": f"{coin} hit new 24h high ฿{price:,.0f}",
                })
        if low_24h > 0 and price <= low_24h * 1.001:  # Within 0.1% of low
            if not _already_fired(coin, "NEW_LOW_24H"):
                events.append({
                    "time": now_str, "coin": coin, "type": "NEW_LOW_24H",
                    "magnitude": round(coin_data.get("change_24h", 0), 2),
                    "description": f"{coin} hit new 24h low ฿{price:,.0f}",
                })

    return events


# ─── Core: Single Tick ────────────────────────────────────────

def do_tick(client: BitkubClient, coins: List[str], verbose: bool = True) -> Dict:
    """Execute one polling cycle: fetch → save → detect → alert."""
    snapshot = poll_ticker(client, coins)

    # Save snapshot
    append_jsonl(snapshot_path(), snapshot)

    # Load today's history for event detection
    history = read_jsonl(snapshot_path())

    # Detect events
    events = detect_events(snapshot, history, WATCHER_CONFIG)

    # Save and alert on events
    for event in events:
        append_jsonl(event_path(), event)
        if WATCHER_CONFIG.get("telegram_alerts"):
            icon = {"PRICE_DROP_1H": "🔴", "PRICE_SPIKE_1H": "🟢",
                    "PRICE_DROP_4H": "🔴📉", "PRICE_SPIKE_4H": "🟢📈",
                    "VOLUME_SPIKE": "📊", "NEW_HIGH_24H": "🚀", "NEW_LOW_24H": "💀"}
            send_telegram(
                f"{icon.get(event['type'], '⚡')} *{event['coin']}* {event['type']}\n"
                f"{event['description']}"
            )

    if verbose:
        ts_str = datetime.fromtimestamp(snapshot["ts"]).strftime("%H:%M:%S")
        print(f"[{ts_str}] Tick OK — {len(snapshot['coins'])} coins, {len(events)} events")
        for coin, d in snapshot["coins"].items():
            print(f"  {coin}: ฿{d['price']:,.2f} ({d['change_24h']:+.2f}%)")
        for ev in events:
            print(f"  ⚡ {ev['coin']}: {ev['type']} — {ev['description']}")

    return snapshot


# ─── Commands ─────────────────────────────────────────────────

def cmd_tick():
    """Single poll — designed for cron: */5 * * * *"""
    client = BitkubClient()
    coins = load_watchlist()
    do_tick(client, coins)


def cmd_daemon():
    """Continuous polling loop."""
    client = BitkubClient()
    coins = load_watchlist()
    interval = WATCHER_CONFIG["interval_seconds"]

    print(f"🔭 Watcher daemon started — polling every {interval}s")
    print(f"   Watching: {', '.join(coins)}")
    print(f"   Data dir: {DATA_DIR}")
    print(f"   Press Ctrl+C to stop\n")

    running = True

    def handle_stop(sig, frame):
        nonlocal running
        print("\n🛑 Stopping watcher...")
        running = False

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    while running:
        try:
            do_tick(client, coins)
        except Exception as e:
            print(f"  ⚠️  Tick error: {e}")
        if running:
            time.sleep(interval)

    print("Watcher stopped.")


def cmd_status():
    """Show watcher status: last tick, snapshot count, events today."""
    date = today_str()
    snapshots = read_jsonl(snapshot_path(date))
    events = read_jsonl(event_path(date))

    print(f"📊 Watcher Status — {date}")
    print(f"   Snapshots today: {len(snapshots)}")
    print(f"   Events today:    {len(events)}")

    if snapshots:
        last = snapshots[-1]
        ts_str = datetime.fromtimestamp(last["ts"]).strftime("%H:%M:%S")
        print(f"   Last tick:       {ts_str}")
        for coin, d in last.get("coins", {}).items():
            print(f"     {coin}: ฿{d['price']:,.2f} ({d['change_24h']:+.2f}%)")
    else:
        print("   No snapshots yet. Run: python watcher.py --tick")

    if events:
        print(f"\n   Recent events:")
        for ev in events[-5:]:
            print(f"     {ev.get('time', '?')} {ev['coin']}: {ev['type']} — {ev['description']}")


def cmd_summary():
    """Generate and display today's context summary."""
    from core.market_context import MarketContext
    ctx = MarketContext.load_today()
    if not ctx:
        print("No data for today. Run watcher first: python watcher.py --tick")
        return

    print(f"📋 Market Context — {ctx.get('date', today_str())}")
    for coin, data in ctx.get("coins", {}).items():
        print(f"\n  {coin}:")
        print(f"    Range: ฿{data.get('low', 0):,.2f} – ฿{data.get('high', 0):,.2f}")
        print(f"    Open/Close: ฿{data.get('open', 0):,.2f} → ฿{data.get('close', 0):,.2f}")
        print(f"    Regime: {data.get('regime', '?')} | Volatility: {data.get('volatility', '?')}")
        if data.get("summary"):
            print(f"    Summary: {data['summary']}")

    if ctx.get("market_sentiment"):
        print(f"\n  Overall: {ctx['market_sentiment']}")


# ─── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Market Watcher — 24/7 Bitkub price monitor")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tick", action="store_true", help="Single poll (cron-friendly)")
    group.add_argument("--daemon", action="store_true", help="Continuous polling loop")
    group.add_argument("--status", action="store_true", help="Show watcher status")
    group.add_argument("--summary", action="store_true", help="Generate/show today's summary")

    args = parser.parse_args()

    if args.tick:
        cmd_tick()
    elif args.daemon:
        cmd_daemon()
    elif args.status:
        cmd_status()
    elif args.summary:
        cmd_summary()


if __name__ == "__main__":
    main()
