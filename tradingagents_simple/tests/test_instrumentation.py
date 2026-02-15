"""Verify event bus imports work from all instrumented modules."""
from core.event_bus import EventBus


def test_event_bus_importable_from_all_modules():
    from agents.team import AgentTeam
    from agents.debate.orchestrator import DebateOrchestrator
    from core.risk_manager import RiskManager
    from core.llm import LLMInterface
    from core.broker import BrokerInterface
    assert True


def test_risk_manager_emits_event():
    bus = EventBus.instance()
    bus.clear()
    from core.risk_manager import RiskManager
    rm = RiskManager()
    decision = {
        "ticker": "BTC",
        "decision": "BUY",
        "confidence": 0.8,
        "current_price": 50000,
    }
    rm.evaluate(decision)
    events = bus.get_events()
    risk_events = [e for e in events if e["source"] == "risk_manager"]
    assert len(risk_events) >= 1


def test_broker_emits_event():
    bus = EventBus.instance()
    bus.clear()
    from core.broker import BrokerInterface
    broker = BrokerInterface(mode="dry_run")
    risk_result = {
        "approved": True,
        "action": "BUY",
        "ticker": "BTC",
        "shares": 0.001,
        "position_size": 50,
        "stop_loss": 49000,
        "take_profit": 52000,
    }
    broker.execute(risk_result)
    events = bus.get_events()
    broker_events = [e for e in events if e["source"] == "broker"]
    assert len(broker_events) >= 1
