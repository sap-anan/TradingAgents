# Architecture Monitor — PowerFactory Dynamic Model Diagram

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a full-screen animated 2D dynamic model diagram (DigSILENT PowerFactory style) to the Streamlit dashboard, showing live data flow between all trading system components.

**Architecture:** Event bus singleton captures system events (agent start/complete, LLM calls, risk checks, broker orders). A new "Architecture" tab embeds an HTML5 Canvas via `st.components.v1.html()` that renders dynamic blocks with input/output terminals, animated signal lines with flow particles, and live values — all at 60fps.

**Tech Stack:** Python (event bus), HTML5 Canvas + vanilla JS (rendering), Streamlit `components.v1.html()` (embedding)

---

### Task 1: Event Bus Module

**Files:**
- Create: `tradingagents_simple/core/event_bus.py`
- Test: `tradingagents_simple/tests/test_event_bus.py`

**Step 1: Create test directory and write failing test**

```bash
mkdir -p tradingagents_simple/tests
touch tradingagents_simple/tests/__init__.py
```

```python
# tradingagents_simple/tests/test_event_bus.py
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
    assert len(events) == 500  # max buffer size
    assert events[0]["value"] == 100  # oldest kept


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
```

**Step 2: Run test to verify it fails**

Run: `cd tradingagents_simple && python -m pytest tests/test_event_bus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.event_bus'`

**Step 3: Implement event bus**

```python
# tradingagents_simple/core/event_bus.py
"""
Event Bus — singleton that captures system events for architecture visualization.
Circular buffer of last 500 events. Thread-safe.
"""
import threading
from collections import deque
from datetime import datetime
from typing import Dict, Any, List, Optional


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

    def emit(
        self,
        source: str,
        target: str,
        signal: str,
        value: Any,
        *,
        latency_ms: int = 0,
        status: str = "ok",
    ):
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
```

**Step 4: Run test to verify it passes**

Run: `cd tradingagents_simple && python -m pytest tests/test_event_bus.py -v`
Expected: All 5 PASS

**Step 5: Commit**

```bash
git add tradingagents_simple/core/event_bus.py tradingagents_simple/tests/
git commit -m "feat: add event bus singleton for architecture monitoring"
```

---

### Task 2: Instrument Agents with Event Bus

**Files:**
- Modify: `tradingagents_simple/agents/team.py`
- Modify: `tradingagents_simple/agents/debate/orchestrator.py`
- Modify: `tradingagents_simple/core/risk_manager.py`
- Modify: `tradingagents_simple/core/llm.py`
- Modify: `tradingagents_simple/core/broker.py`
- Test: `tradingagents_simple/tests/test_instrumentation.py`

**Step 1: Write failing test**

```python
# tradingagents_simple/tests/test_instrumentation.py
"""Verify that event bus receives events from instrumented components."""
from core.event_bus import EventBus


def test_event_bus_importable_from_all_modules():
    """Smoke test: all instrumented modules import event_bus without error."""
    from agents.team import AgentTeam
    from agents.debate.orchestrator import DebateOrchestrator
    from core.risk_manager import RiskManager
    from core.llm import LLMInterface
    from core.broker import BrokerInterface
    # If we get here, all imports work
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
        "price": 50000,
    }
    rm.evaluate(decision)
    events = bus.get_events()
    risk_events = [e for e in events if e["source"] == "risk_manager"]
    assert len(risk_events) >= 1
```

**Step 2: Run test to verify it fails**

Run: `cd tradingagents_simple && python -m pytest tests/test_instrumentation.py -v`
Expected: `test_risk_manager_emits_event` FAIL (no events emitted yet)

**Step 3: Add instrumentation to each module**

Add to top of each file: `from core.event_bus import EventBus`

**`agents/team.py`** — In `analyze_and_decide()`, after each agent runs:
```python
EventBus.instance().emit(
    agent.name, "debate", "score",
    view.get("confidence", 0),
    latency_ms=int(elapsed_ms),
    status="running",
)
```

**`agents/debate/orchestrator.py`** — After each debate round:
```python
EventBus.instance().emit(
    "debate", "risk_manager", "decision",
    {"signal": verdict.get("decision"), "confidence": verdict.get("confidence")},
    latency_ms=int(elapsed_ms),
    status="running",
)
```

**`core/risk_manager.py`** — In `evaluate()`:
```python
EventBus.instance().emit(
    "risk_manager", "broker", "risk_check",
    {"approved": approved, "risk_pct": risk_pct},
    status="pass" if approved else "reject",
)
```

**`core/llm.py`** — In the call method, after response:
```python
EventBus.instance().emit(
    "llm", caller or "agent", "response",
    {"tokens_in": tokens_in, "tokens_out": tokens_out},
    latency_ms=int(elapsed * 1000),
    status="ok",
)
```

**`core/broker.py`** — In order execution:
```python
EventBus.instance().emit(
    "broker", "output", "order",
    {"action": action, "ticker": ticker, "qty": qty},
    status="ok",
)
```

**Step 4: Run test to verify it passes**

Run: `cd tradingagents_simple && python -m pytest tests/test_instrumentation.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add tradingagents_simple/agents/ tradingagents_simple/core/
git commit -m "feat: instrument agents, risk, llm, broker with event bus"
```

---

### Task 3: Canvas Renderer — PowerFactory Dynamic Model Diagram

**Files:**
- Create: `tradingagents_simple/components/architecture_canvas.py`

This is the largest task — the full HTML5 Canvas + JS that renders the PowerFactory-style diagram.

**Step 1: Create the component**

```python
# tradingagents_simple/components/__init__.py
```

```python
# tradingagents_simple/components/architecture_canvas.py
"""
PowerFactory-style dynamic model diagram renderer.
Returns HTML string for st.components.v1.html().
"""
from typing import Dict, List, Any


def render_architecture_html(events: List[Dict], node_statuses: Dict[str, str], width: int = 1400, height: int = 800) -> str:
    """Generate the full HTML/JS/Canvas for the architecture diagram."""

    # Serialize events to JSON for JS consumption
    import json
    events_json = json.dumps(events[-50:])  # last 50 events for animation
    statuses_json = json.dumps(node_statuses)

    return f"""
<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0f1218; overflow: hidden; font-family: 'Consolas', 'Monaco', monospace; }}
  canvas {{ display: block; cursor: grab; }}
  canvas:active {{ cursor: grabbing; }}
  #tooltip {{
    position: absolute; display: none; background: #1c2030; border: 1px solid #3a4560;
    border-radius: 6px; padding: 10px 14px; color: #c0c8d8; font-size: 11px;
    pointer-events: none; z-index: 100; max-width: 300px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  }}
  #tooltip .label {{ color: #7a8aaa; font-size: 10px; margin-bottom: 4px; }}
  #tooltip .value {{ color: #00e676; font-size: 13px; font-weight: bold; }}
</style>
</head>
<body>
<canvas id="c"></canvas>
<div id="tooltip"></div>
<script>
// ─── DATA ───
const events = {events_json};
const nodeStatuses = {statuses_json};

// ─── CANVAS SETUP ───
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const tooltip = document.getElementById('tooltip');
const dpr = window.devicePixelRatio || 1;

function resize() {{
  canvas.width = {width} * dpr;
  canvas.height = {height} * dpr;
  canvas.style.width = {width} + 'px';
  canvas.style.height = {height} + 'px';
  ctx.scale(dpr, dpr);
}}
resize();

// ─── PAN & ZOOM ───
let panX = 0, panY = 0, zoom = 1;
let dragging = false, dragStartX = 0, dragStartY = 0;

canvas.addEventListener('mousedown', e => {{
  dragging = true; dragStartX = e.clientX - panX; dragStartY = e.clientY - panY;
}});
canvas.addEventListener('mousemove', e => {{
  if (dragging) {{ panX = e.clientX - dragStartX; panY = e.clientY - dragStartY; }}
  checkHover(e);
}});
canvas.addEventListener('mouseup', () => {{ dragging = false; }});
canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  const delta = e.deltaY > 0 ? 0.9 : 1.1;
  zoom = Math.max(0.3, Math.min(3, zoom * delta));
}}, {{ passive: false }});

// ─── NODE DEFINITIONS (PowerFactory blocks) ───
const nodes = [
  {{ id: 'market_data', label: 'MARKET DATA', sub: ['Bitkub WS', 'REST API'], type: 'data',
     x: 80, y: 300, w: 180, h: 120, color: '#4a9eff',
     inputs: [], outputs: ['price', 'vol', 'ohlcv'] }},
  {{ id: 'fundamental', label: 'FUNDAMENTAL', sub: ['Valuation', 'Growth', 'Catalyst'], type: 'analysis',
     x: 380, y: 100, w: 180, h: 130, color: '#00c853',
     inputs: ['price', 'vol'], outputs: ['score'] }},
  {{ id: 'technical', label: 'TECHNICAL', sub: ['RSI(14)', 'MACD', 'Bollinger'], type: 'analysis',
     x: 380, y: 280, w: 180, h: 130, color: '#00c853',
     inputs: ['price', 'ohlcv'], outputs: ['score'] }},
  {{ id: 'sentiment', label: 'SENTIMENT', sub: ['News NLP', 'Social'], type: 'analysis',
     x: 380, y: 460, w: 180, h: 120, color: '#00c853',
     inputs: ['price'], outputs: ['score'] }},
  {{ id: 'debate', label: 'DEBATE ENGINE', sub: ['Bull Agent', 'Bear Agent', 'Moderator'], type: 'decision',
     x: 700, y: 260, w: 190, h: 140, color: '#ff9100',
     inputs: ['scores'], outputs: ['decision'] }},
  {{ id: 'risk_manager', label: 'RISK MANAGER', sub: ['Position', 'Exposure', 'Stop-Loss'], type: 'risk',
     x: 1000, y: 280, w: 180, h: 130, color: '#ff1744',
     inputs: ['decision'], outputs: ['order'] }},
  {{ id: 'broker', label: 'BROKER', sub: ['Order Exec'], type: 'output',
     x: 1250, y: 310, w: 140, h: 90, color: '#aa00ff',
     inputs: ['order'], outputs: [] }},
  {{ id: 'llm', label: 'LLM PROVIDER', sub: ['Gemini', 'DeepSeek'], type: 'infra',
     x: 550, y: 580, w: 170, h: 100, color: '#00e5ff',
     inputs: ['prompt'], outputs: ['response'] }},
];

// ─── SIGNAL LINES (connections) ───
const connections = [
  {{ from: 'market_data', to: 'fundamental', signal: 'price[]', fromPort: 0, toPort: 0 }},
  {{ from: 'market_data', to: 'technical', signal: 'ohlcv[]', fromPort: 1, toPort: 0 }},
  {{ from: 'market_data', to: 'sentiment', signal: 'price[]', fromPort: 2, toPort: 0 }},
  {{ from: 'fundamental', to: 'debate', signal: 'score', fromPort: 0, toPort: 0 }},
  {{ from: 'technical', to: 'debate', signal: 'score', fromPort: 0, toPort: 0 }},
  {{ from: 'sentiment', to: 'debate', signal: 'score', fromPort: 0, toPort: 0 }},
  {{ from: 'debate', to: 'risk_manager', signal: 'decision', fromPort: 0, toPort: 0 }},
  {{ from: 'risk_manager', to: 'broker', signal: 'order', fromPort: 0, toPort: 0 }},
  {{ from: 'llm', to: 'fundamental', signal: 'response', fromPort: 0, toPort: 1 }},
  {{ from: 'llm', to: 'technical', signal: 'response', fromPort: 0, toPort: 1 }},
  {{ from: 'llm', to: 'sentiment', signal: 'response', fromPort: 0, toPort: 1 }},
  {{ from: 'llm', to: 'debate', signal: 'response', fromPort: 0, toPort: 1 }},
];

// ─── FLOW PARTICLES ───
let particles = [];
function spawnParticle(conn) {{
  particles.push({{ conn, t: 0, speed: 0.005 + Math.random() * 0.005 }});
}}

// Spawn particles periodically
let spawnTimer = 0;

// ─── EXTRACT LIVE VALUES FROM EVENTS ───
function getSignalValue(source, target, signal) {{
  for (let i = events.length - 1; i >= 0; i--) {{
    const e = events[i];
    if (e.source === source && e.target === target) {{
      if (typeof e.value === 'number') return e.value.toFixed(2);
      if (typeof e.value === 'object' && e.value !== null) {{
        if (e.value.signal) return e.value.signal;
        if (e.value.approved !== undefined) return e.value.approved ? 'PASS' : 'REJECT';
      }}
      return String(e.value).substring(0, 12);
    }}
  }}
  return '';
}}

function getNodeLatency(nodeId) {{
  for (let i = events.length - 1; i >= 0; i--) {{
    if (events[i].source === nodeId && events[i].latency_ms) return events[i].latency_ms + 'ms';
  }}
  return '';
}}

// ─── HOVER DETECTION ───
let hoveredNode = null;
function checkHover(e) {{
  const rect = canvas.getBoundingClientRect();
  const mx = (e.clientX - rect.left - panX) / zoom;
  const my = (e.clientY - rect.top - panY) / zoom;
  hoveredNode = null;
  for (const n of nodes) {{
    if (mx >= n.x && mx <= n.x + n.w && my >= n.y && my <= n.y + n.h) {{
      hoveredNode = n;
      const lat = getNodeLatency(n.id);
      const st = nodeStatuses[n.id] || 'idle';
      tooltip.style.display = 'block';
      tooltip.style.left = (e.clientX + 15) + 'px';
      tooltip.style.top = (e.clientY + 15) + 'px';
      tooltip.innerHTML = `<div class="label">${{n.label}}</div>` +
        `<div class="value">Status: ${{st}}</div>` +
        (lat ? `<div class="value">Latency: ${{lat}}</div>` : '') +
        `<div class="label" style="margin-top:6px">Sub-blocks: ${{n.sub.join(', ')}}</div>`;
      return;
    }}
  }}
  tooltip.style.display = 'none';
}}

// ─── DRAW FUNCTIONS ───

function drawGrid() {{
  ctx.fillStyle = '#0f1218';
  ctx.fillRect(0, 0, {width}, {height});
  ctx.save();
  ctx.translate(panX, panY);
  ctx.scale(zoom, zoom);
  // Dot grid
  ctx.fillStyle = '#1a1f2e';
  for (let x = 0; x < 2000; x += 30) {{
    for (let y = 0; y < 1000; y += 30) {{
      ctx.fillRect(x, y, 1, 1);
    }}
  }}
}}

function drawNode(n) {{
  const st = nodeStatuses[n.id] || 'idle';
  const isHovered = hoveredNode && hoveredNode.id === n.id;

  // Shadow / glow
  if (st === 'running' || st === 'ok') {{
    ctx.shadowColor = n.color;
    ctx.shadowBlur = isHovered ? 20 : 8;
  }}

  // Block background
  ctx.fillStyle = '#1c2030';
  ctx.strokeStyle = isHovered ? n.color : '#3a4560';
  ctx.lineWidth = isHovered ? 2 : 1;
  roundRect(ctx, n.x, n.y, n.w, n.h, 6);
  ctx.fill();
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Header bar
  ctx.fillStyle = n.color;
  ctx.fillRect(n.x + 1, n.y + 1, n.w - 2, 24);
  // Header text
  ctx.fillStyle = '#0f1218';
  ctx.font = 'bold 11px Consolas, Monaco, monospace';
  ctx.fillText(n.label, n.x + 8, n.y + 16);

  // Sub-blocks
  ctx.fillStyle = '#2a3040';
  const subY = n.y + 32;
  const subH = 18;
  n.sub.forEach((s, i) => {{
    const sy = subY + i * (subH + 3);
    roundRect(ctx, n.x + 8, sy, n.w - 16, subH, 3);
    ctx.fill();
    ctx.fillStyle = '#8a94a8';
    ctx.font = '10px Consolas, Monaco, monospace';
    ctx.fillText(s, n.x + 14, sy + 13);
    ctx.fillStyle = '#2a3040';
  }});

  // Status dot
  const dotColor = st === 'running' || st === 'ok' || st === 'pass' ? '#00e676'
    : st === 'error' || st === 'reject' ? '#ff1744' : '#555';
  ctx.beginPath();
  ctx.arc(n.x + 12, n.y + n.h - 10, 4, 0, Math.PI * 2);
  ctx.fillStyle = dotColor;
  ctx.fill();
  // Glow on active
  if (st === 'running' || st === 'ok') {{
    ctx.beginPath();
    ctx.arc(n.x + 12, n.y + n.h - 10, 7, 0, Math.PI * 2);
    ctx.fillStyle = dotColor + '33';
    ctx.fill();
  }}

  // Status label
  ctx.fillStyle = '#6a7488';
  ctx.font = '9px Consolas, Monaco, monospace';
  const latency = getNodeLatency(n.id);
  ctx.fillText((st === 'idle' ? 'IDLE' : st.toUpperCase()) + (latency ? ' ' + latency : ''), n.x + 22, n.y + n.h - 6);

  // Input terminals (left)
  n.inputs.forEach((inp, i) => {{
    const ty = n.y + 35 + i * 25;
    ctx.beginPath();
    ctx.arc(n.x, ty, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#3a4560';
    ctx.fill();
    ctx.strokeStyle = '#5a6580';
    ctx.lineWidth = 1;
    ctx.stroke();
  }});

  // Output terminals (right)
  n.outputs.forEach((out, i) => {{
    const ty = n.y + 35 + i * 25;
    ctx.beginPath();
    ctx.arc(n.x + n.w, ty, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#3a4560';
    ctx.fill();
    ctx.strokeStyle = '#5a6580';
    ctx.lineWidth = 1;
    ctx.stroke();
  }});
}}

function drawConnection(conn) {{
  const fromNode = nodes.find(n => n.id === conn.from);
  const toNode = nodes.find(n => n.id === conn.to);
  if (!fromNode || !toNode) return;

  const x1 = fromNode.x + fromNode.w;
  const y1 = fromNode.y + 35 + conn.fromPort * 25;
  const x2 = toNode.x;
  const y2 = toNode.y + 35 + conn.toPort * 25;

  // Bezier curve
  const cpx = (x1 + x2) / 2;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.bezierCurveTo(cpx, y1, cpx, y2, x2, y2);
  ctx.strokeStyle = '#4a5568';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Arrow at end
  const angle = Math.atan2(y2 - y1, x2 - (cpx));
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - 8, y2 - 4);
  ctx.lineTo(x2 - 8, y2 + 4);
  ctx.closePath();
  ctx.fillStyle = '#4a5568';
  ctx.fill();

  // Signal label + live value
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2 - 8;
  const liveVal = getSignalValue(conn.from, conn.to, conn.signal);
  ctx.font = '9px Consolas, Monaco, monospace';
  ctx.fillStyle = '#5a6a80';
  ctx.fillText(conn.signal, midX - 15, midY);
  if (liveVal) {{
    ctx.fillStyle = '#00e676';
    ctx.font = 'bold 10px Consolas, Monaco, monospace';
    ctx.fillText(liveVal, midX - 15, midY + 13);
  }}
}}

function drawParticles() {{
  particles = particles.filter(p => p.t <= 1);
  particles.forEach(p => {{
    p.t += p.speed;
    const conn = p.conn;
    const fromNode = nodes.find(n => n.id === conn.from);
    const toNode = nodes.find(n => n.id === conn.to);
    if (!fromNode || !toNode) return;

    const x1 = fromNode.x + fromNode.w;
    const y1 = fromNode.y + 35 + conn.fromPort * 25;
    const x2 = toNode.x;
    const y2 = toNode.y + 35 + conn.toPort * 25;
    const cpx = (x1 + x2) / 2;

    // Cubic bezier point
    const t = p.t;
    const mt = 1 - t;
    const px = mt*mt*mt*x1 + 3*mt*mt*t*cpx + 3*mt*t*t*cpx + t*t*t*x2;
    const py = mt*mt*mt*y1 + 3*mt*mt*t*y1 + 3*mt*t*t*y2 + t*t*t*y2;

    ctx.beginPath();
    ctx.arc(px, py, 3, 0, Math.PI * 2);
    ctx.fillStyle = '#00e676';
    ctx.fill();
    // Glow trail
    ctx.beginPath();
    ctx.arc(px, py, 6, 0, Math.PI * 2);
    ctx.fillStyle = '#00e67622';
    ctx.fill();
  }});
}}

function roundRect(ctx, x, y, w, h, r) {{
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}}

// ─── MAIN LOOP ───
function frame() {{
  ctx.save();
  drawGrid();

  // Spawn particles
  spawnTimer++;
  if (spawnTimer % 60 === 0) {{
    connections.forEach(c => {{ if (Math.random() < 0.4) spawnParticle(c); }});
  }}

  connections.forEach(drawConnection);
  drawParticles();
  nodes.forEach(drawNode);

  ctx.restore();
  requestAnimationFrame(frame);
}}
frame();
</script>
</body>
</html>
"""
```

**Step 2: Verify it renders (manual)**

Run: `cd tradingagents_simple && python -c "from components.architecture_canvas import render_architecture_html; html = render_architecture_html([], {{}}); print(f'HTML length: {{len(html)}}')""`
Expected: `HTML length: ~8000+`

**Step 3: Commit**

```bash
git add tradingagents_simple/components/
git commit -m "feat: PowerFactory-style canvas renderer for architecture diagram"
```

---

### Task 4: Integrate Architecture Tab into Dashboard

**Files:**
- Modify: `tradingagents_simple/dashboard.py`

**Step 1: Add the tab**

At the top of `dashboard.py`, add import:
```python
from components.architecture_canvas import render_architecture_html
from core.event_bus import EventBus
```

Change the tabs line from:
```python
tab_trading, tab_watcher, tab_llm = st.tabs(["🦈 Trading Monitor", "📡 Market Watcher", "🤖 LLM Usage"])
```
To:
```python
tab_trading, tab_watcher, tab_llm, tab_arch = st.tabs(["🦈 Trading Monitor", "📡 Market Watcher", "🤖 LLM Usage", "🏗️ Architecture"])
```

Add the Architecture tab content:
```python
# ══════════════════════════════════════════════════════════════
# Tab 4: Architecture — PowerFactory Dynamic Model Diagram
# ══════════════════════════════════════════════════════════════
with tab_arch:
    st.subheader("System Architecture — Dynamic Model Diagram")
    st.caption("DigSILENT PowerFactory-style | Pan: drag | Zoom: scroll | Hover: details")

    bus = EventBus.instance()
    events = bus.get_events(limit=50)
    statuses = bus.get_node_statuses()

    arch_html = render_architecture_html(events, statuses, width=1400, height=750)
    st.components.v1.html(arch_html, height=760, scrolling=False)

    # Event log below canvas
    if events:
        with st.expander(f"Event Log ({len(events)} events)", expanded=False):
            import pandas as pd
            df = pd.DataFrame(events[-20:][::-1])
            st.dataframe(df, use_container_width=True, hide_index=True)
```

**Step 2: Run dashboard to verify**

Run: `cd tradingagents_simple && streamlit run dashboard.py`
Expected: New "Architecture" tab visible with animated PowerFactory diagram.

**Step 3: Commit**

```bash
git add tradingagents_simple/dashboard.py
git commit -m "feat: add Architecture tab with PowerFactory dynamic model diagram"
```

---

### Task 5: Demo Event Generator (for testing without live trading)

**Files:**
- Create: `tradingagents_simple/components/demo_events.py`

**Step 1: Create demo event generator**

```python
# tradingagents_simple/components/demo_events.py
"""Generate fake events so the Architecture tab shows animation without live trading."""
import threading
import time
import random
from core.event_bus import EventBus


def start_demo_events():
    """Background thread that emits realistic demo events every 2-3 seconds."""

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
```

**Step 2: Wire demo mode into dashboard**

In `dashboard.py`, inside `with tab_arch:`, before rendering, add:
```python
    demo_mode = st.checkbox("Demo Mode (simulated events)", value=True)
    if demo_mode and "demo_started" not in st.session_state:
        from components.demo_events import start_demo_events
        start_demo_events()
        st.session_state["demo_started"] = True
```

**Step 3: Run and verify animations work**

Run: `cd tradingagents_simple && streamlit run dashboard.py`
Expected: Architecture tab shows nodes with green status dots, particles flowing, live values updating.

**Step 4: Commit**

```bash
git add tradingagents_simple/components/ tradingagents_simple/dashboard.py
git commit -m "feat: add demo event generator for architecture visualization"
```

---

## Summary

| Task | Description | New Files | Modified Files |
|------|-------------|-----------|---------------|
| 1 | Event Bus | `core/event_bus.py`, `tests/` | — |
| 2 | Instrument agents | — | `agents/team.py`, `agents/debate/orchestrator.py`, `core/risk_manager.py`, `core/llm.py`, `core/broker.py` |
| 3 | Canvas renderer | `components/architecture_canvas.py` | — |
| 4 | Dashboard tab | — | `dashboard.py` |
| 5 | Demo events | `components/demo_events.py` | `dashboard.py` |
