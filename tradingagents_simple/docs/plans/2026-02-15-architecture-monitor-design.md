# Architecture Monitor — PowerFactory-Style Dynamic Model Diagram

**Date**: 2026-02-15
**Status**: Approved
**Location**: New "Architecture" tab in existing `dashboard.py`

## Goal

Full-screen animated 2D dynamic model diagram (DigSILENT PowerFactory style) showing every trading system component as a dynamic block with input/output terminals, connected by signal lines displaying real-time data flow values.

## Architecture

### Rendering

- HTML5 Canvas embedded via `st.components.v1.html()` in a new Streamlit tab
- 60fps animation via `requestAnimationFrame`
- Device pixel ratio scaling for crisp high-resolution rendering
- Pan (mouse drag) and zoom (scroll wheel) like PowerFactory canvas

### Dynamic Model Blocks

Each system component rendered as a PowerFactory-style frame:

| Component | Type Color | Internal Sub-blocks |
|-----------|-----------|-------------------|
| Market Data (Bitkub WS + REST) | Blue `#4a9eff` | WebSocket, REST API |
| Fundamental Analyst | Green `#00c853` | Valuation, Growth, Catalyst |
| Technical Analyst | Green `#00c853` | RSI(14), MACD, Bollinger |
| Sentiment Analyst | Green `#00c853` | News NLP, Social |
| Debate Engine | Orange `#ff9100` | Bull Agent, Bear Agent, Moderator |
| Risk Manager | Red `#ff1744` | Position, Exposure, Stop-Loss |
| Broker | Purple `#aa00ff` | Order execution |
| LLM Provider | Cyan `#00e5ff` | Gemini / DeepSeek |

**Block anatomy:**
- Header bar (colored by type, component name)
- Internal sub-blocks (nested modules visible inside)
- Input terminals (left edge, small circles)
- Output terminals (right edge, small circles)
- Status indicator dot (bottom-left): green=running, gray=idle, red=error
- Performance label (bottom): latency, sample rate

### Signal Lines

- Solid lines with directional arrows
- Signal label on each line: variable name + live current value
- Line color: white=normal, amber=delayed, red=error
- Animated flow dots traveling along lines (speed ∝ data rate)
- Line thickness ∝ data volume (thin=scalar, thick=array)

### Data Flow Path

```
Market Data ──price[],vol[],ohlcv[]──▶ Fundamental ──score──╗
                                      Technical  ──score──╬──▶ Debate ──decision──▶ Risk ──order──▶ Broker
                                      Sentiment  ──score──╝
                                           ▲
                                      LLM Provider (prompt/response on each analyst + debate)
```

### Interactive Features

- **Pan & zoom**: mouse drag + scroll wheel
- **Click block**: expand to show internal parameters, LLM prompt/response, timing
- **Hover signal line**: tooltip with last 10 values as mini sparkline
- **Zoom-dependent detail**: zoom in = sub-block internals + parameter tables; zoom out = simplified view

## Event Bus (Python side)

New module `core/event_bus.py` — singleton that captures system events:

```python
{
    "timestamp": "2026-02-15T14:30:01.234",
    "source": "technical",
    "target": "debate",
    "signal": "score",
    "value": 0.65,
    "latency_ms": 180,
    "status": "ok"
}
```

Events stored in a circular buffer (last 500), exposed to Streamlit via `st.session_state`.

Instrumentation points:
- Each analyst agent emits events on start/complete
- Debate engine emits on each agent turn + final decision
- Risk manager emits on check start/pass/reject
- Broker emits on order submit/fill/error
- LLM calls emit on request/response with token counts

## Visual Style

- Background: `#0f1218` with subtle dot grid
- Block fill: `#1c2030`, border `1px solid #3a4560`
- Header bars: colored by component type (see table above)
- Signal lines: `#7a8aaa` default, animated dots `#00e676`
- Values on lines: monospace `#c0c8d8` 11px
- Status dots: 6px with glow effect
- Font: monospace throughout for industrial feel

## Integration

- Add `🏗️ Architecture` tab to existing `st.tabs()` in `dashboard.py`
- New files: `core/event_bus.py`, `components/architecture_canvas.py`
- Instrument existing agents/traders to emit events via event bus
- No changes to trading logic — observation only

## Dependencies

- No new pip packages (pure HTML5 Canvas + vanilla JS)
- Streamlit `components.v1.html()` (already available)
