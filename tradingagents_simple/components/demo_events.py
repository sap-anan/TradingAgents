"""Generate fake events so the Architecture tab shows animation without live trading."""
import threading
import time
import random
from core.event_bus import EventBus


def start_demo_events():
    """Background thread that emits realistic demo events every 0.5-1.5 seconds."""

    def _run():
        bus = EventBus.instance()
        cycle = [
            ("market_data", "fundamental", "price", lambda: round(random.uniform(40000, 60000), 2)),
            ("market_data", "technical", "ohlcv", lambda: "candle"),
            ("market_data", "sentiment", "price", lambda: round(random.uniform(40000, 60000), 2)),
            ("llm", "fundamental", "response", lambda: {"tokens_in": random.randint(200, 800), "tokens_out": random.randint(100, 400)}),
            ("fundamental", "debate", "score", lambda: round(random.uniform(0.3, 0.9), 2)),
            ("llm", "technical", "response", lambda: {"tokens_in": random.randint(200, 800), "tokens_out": random.randint(100, 400)}),
            ("technical", "debate", "score", lambda: round(random.uniform(0.3, 0.9), 2)),
            ("llm", "sentiment", "response", lambda: {"tokens_in": random.randint(100, 500), "tokens_out": random.randint(50, 200)}),
            ("sentiment", "debate", "score", lambda: round(random.uniform(0.3, 0.9), 2)),
            ("llm", "debate", "response", lambda: {"tokens_in": random.randint(500, 1500), "tokens_out": random.randint(200, 600)}),
            ("debate", "risk_manager", "decision", lambda: {"signal": random.choice(["BUY", "SELL", "HOLD"]), "confidence": round(random.uniform(0.5, 0.95), 2)}),
            ("risk_manager", "broker", "risk_check", lambda: {"approved": random.random() > 0.3}),
        ]
        while True:
            for source, target, signal, value_fn in cycle:
                bus.emit(source, target, signal, value_fn(),
                         latency_ms=random.randint(50, 2000),
                         status="running")
                time.sleep(random.uniform(0.5, 1.5))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
