"""Generate demo events for Architecture tab — one full pipeline cycle."""
import threading
import time
import random
from core.event_bus import EventBus


def run_demo_cycle():
    """Run ONE full pipeline cycle in background (~20 seconds), then stop.

    Simulates: Market Data → Analysts → LLM calls → Debate → Risk → Broker
    """

    def _run():
        bus = EventBus.instance()
        bus.clear()

        # Stage 1: Market Data intake
        _step(bus, "market_data", "fundamental", "price", round(random.uniform(40000, 60000), 2), 50)
        _step(bus, "market_data", "technical", "ohlcv", "candle", 30)
        _step(bus, "market_data", "sentiment", "price", round(random.uniform(40000, 60000), 2), 20)

        # Stage 2: LLM calls for each analyst
        _step(bus, "llm", "fundamental", "response",
              {"tokens_in": random.randint(300, 800), "tokens_out": random.randint(150, 400)}, 800)
        _step(bus, "fundamental", "debate", "score", round(random.uniform(0.5, 0.9), 2), 180)

        _step(bus, "llm", "technical", "response",
              {"tokens_in": random.randint(300, 800), "tokens_out": random.randint(150, 400)}, 650)
        _step(bus, "technical", "debate", "score", round(random.uniform(0.4, 0.85), 2), 150)

        _step(bus, "llm", "sentiment", "response",
              {"tokens_in": random.randint(200, 600), "tokens_out": random.randint(100, 300)}, 500)
        _step(bus, "sentiment", "debate", "score", round(random.uniform(0.3, 0.8), 2), 200)

        # Stage 3: Debate rounds
        _step(bus, "llm", "debate", "response",
              {"tokens_in": random.randint(800, 1500), "tokens_out": random.randint(300, 600)}, 1200)
        _step(bus, "debate", "debate", "bull_round", round(random.uniform(0.6, 0.9), 2), 400)
        _step(bus, "debate", "debate", "bear_round", round(random.uniform(0.5, 0.85), 2), 350)

        # Stage 4: Final decision
        signal = random.choice(["BUY", "SELL", "HOLD"])
        confidence = round(random.uniform(0.55, 0.92), 2)
        _step(bus, "debate", "risk_manager", "decision",
              {"signal": signal, "confidence": confidence}, 100)

        # Stage 5: Risk check
        approved = confidence > 0.6
        _step(bus, "risk_manager", "broker", "risk_check",
              {"approved": approved, "action": signal},
              50, status="pass" if approved else "reject")

        # Stage 6: Broker execution (if approved)
        if approved:
            _step(bus, "broker", "output", "order",
                  {"action": signal, "ticker": "BTC", "shares": round(random.uniform(0.001, 0.05), 4)}, 30)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _step(bus, source, target, signal, value, latency_ms, status="running"):
    """Emit one event with realistic delay."""
    time.sleep(latency_ms / 1000 * random.uniform(0.8, 1.5))
    bus.emit(source, target, signal, value, latency_ms=latency_ms, status=status)
