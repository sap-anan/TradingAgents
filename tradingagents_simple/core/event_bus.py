"""
Event Bus — singleton that captures system events for architecture visualization.
Circular buffer of last 500 events. Thread-safe.
"""
import threading
from collections import deque
from datetime import datetime
from typing import Dict, Any, List


class EventBus:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._events: deque = deque(maxlen=500)
        self._node_statuses: Dict[str, str] = {}
        self._emit_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "EventBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def emit(self, source: str, target: str, signal: str, value: Any, *, latency_ms: int = 0, status: str = "ok"):
        event = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "target": target,
            "signal": signal,
            "value": value,
            "latency_ms": latency_ms,
            "status": status,
        }
        with self._emit_lock:
            self._events.append(event)
            self._node_statuses[source] = status

    def get_events(self, limit: int = 500) -> List[Dict]:
        with self._emit_lock:
            return list(self._events)[-limit:]

    def get_node_statuses(self) -> Dict[str, str]:
        with self._emit_lock:
            return dict(self._node_statuses)

    def clear(self):
        with self._emit_lock:
            self._events.clear()
            self._node_statuses.clear()
