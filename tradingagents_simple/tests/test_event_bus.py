from core.event_bus import EventBus


def test_singleton():
    a = EventBus.instance()
    b = EventBus.instance()
    assert a is b


def test_emit_and_get_events():
    bus = EventBus.instance()
    bus.clear()
    bus.emit("market_data", "technical", "score", 0.72, latency_ms=180)
    events = bus.get_events()
    assert len(events) == 1
    e = events[0]
    assert e["source"] == "market_data"
    assert e["target"] == "technical"
    assert e["signal"] == "score"
    assert e["value"] == 0.72
    assert e["latency_ms"] == 180
    assert e["status"] == "ok"
    assert "timestamp" in e


def test_circular_buffer_limit():
    bus = EventBus.instance()
    bus.clear()
    for i in range(600):
        bus.emit("src", "tgt", "sig", i)
    events = bus.get_events()
    assert len(events) == 500
    assert events[0]["value"] == 100


def test_get_node_status():
    bus = EventBus.instance()
    bus.clear()
    bus.emit("market_data", "technical", "price", 100.0, status="running")
    bus.emit("technical", "debate", "score", 0.7, status="running")
    statuses = bus.get_node_statuses()
    assert statuses["market_data"] == "running"
    assert statuses["technical"] == "running"


def test_emit_error_status():
    bus = EventBus.instance()
    bus.clear()
    bus.emit("llm", "technical", "response", None, status="error", latency_ms=5000)
    events = bus.get_events()
    assert events[0]["status"] == "error"
