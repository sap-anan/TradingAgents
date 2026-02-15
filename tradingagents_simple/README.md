# TradingAgents Simple — Agentic Trading System

> *"Don't trust a single voice. Let them debate, then decide."*

A **progressive, multi-agent AI trading system** built from scratch — from a single rule-based agent to a full production pipeline with Bull vs Bear debates, risk management, and 24/7 market monitoring.

---

## 🧠 The Mindset

### Why Multi-Agent?

A single AI analyzing a stock is like asking one person for advice — you get one perspective. Real trading desks don't work that way. They have **specialists who disagree**, **researchers who debate**, and **risk managers who veto**.

This system mirrors that dynamic:

```
One AI opinion  →  Three specialist analysts  →  Adversarial debate  →  Judge decides  →  Risk gate  →  Execute
```

### Core Principles

| Principle | How We Apply It |
|-----------|----------------|
| **Progressive Complexity** | 5 phases — start simple, add layers only when needed |
| **Adversarial Reasoning** | Bull vs Bear debate forces balanced analysis |
| **Safety First** | Risk Manager has absolute veto power over any trade |
| **Cost Efficiency** | Gemini free tier + DeepSeek ($0.14/M tokens) — not GPT-4 prices |
| **Memory & Learning** | Track every decision, measure every agent's accuracy, improve over time |
| **Transparency** | Every decision shows full reasoning chain — never a black box |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     📥  TICKER INPUT                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  📊  DATA LAYER                                                 │
│  yfinance (stocks) │ Bitkub API (crypto/THB) │ WebSocket live   │
│  → price, volume, RSI, SMA, volatility, intraday context        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  🔬  ANALYST TEAM (3 Specialists)                               │
│  ┌──────────────┐ ┌────────────────┐ ┌───────────────┐         │
│  │  Technical    │ │  Fundamental   │ │  Sentiment    │         │
│  │  RSI, SMA,   │ │  Valuation,    │ │  News, social │         │
│  │  MACD, trend │ │  growth, P/E   │ │  media mood   │         │
│  └──────┬───────┘ └───────┬────────┘ └──────┬────────┘         │
│         └─────────────────┼─────────────────┘                   │
│                     BULLISH / BEARISH / NEUTRAL                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  ⚔️  DEBATE ENGINE (Bull vs Bear, Multi-Round)                  │
│                                                                  │
│   Round 1:  🐂 Bull argues BUY    →  🐻 Bear rebuts with risks │
│   Round 2:  🐂 Bull counters      →  🐻 Bear doubles down      │
│   Round N:  ...conviction scores evolve each round...            │
│                                                                  │
│   + Intraday Market Context injected from Watcher snapshots      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  ⚖️  JUDGE (Senior Portfolio Manager)                           │
│  Evaluates all debate rounds → Final verdict: BUY / SELL / HOLD │
│  Winner: bull / bear / tie │ Confidence: 0.0 – 1.0              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  🛡️  RISK MANAGER (Veto Power)                                  │
│  ✓ Confidence ≥ threshold?     ✓ Position size within limits?   │
│  ✓ Max positions not exceeded? ✓ Daily loss limit not hit?      │
│  → APPROVED  or  → REJECTED (with reason)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  💰  BROKER (Execution)                                          │
│  dry_run (log only) │ Alpaca paper │ Alpaca live │ Bitkub live  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  🧠  MEMORY + 🔔 ALERTS                                         │
│  Record decision → Track outcome → Update agent accuracy stats  │
│  Console / File / Telegram notifications                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 The 5 Phases

Each phase is a **standalone entry point** — run any phase independently.

### Phase 1: Single Agent (`simple_trader.py`)
```bash
python simple_trader.py NVDA
```
One agent, two modes: **rule-based** (free, no API) or **LLM-powered** analysis. Start here to understand the foundation.

### Phase 2: Agent Team (`team_trader.py`)
```bash
python team_trader.py NVDA
```
Three specialists (Technical, Fundamental, Sentiment) analyze independently, then an LLM synthesizes their views into a consensus.

### Phase 3: Bull vs Bear Debate (`debate_trader.py`)
```bash
python debate_trader.py NVDA --rounds 3
```
The core innovation. Analysts feed their views to a **Bull** and **Bear** researcher who debate across multiple rounds. A **Judge** (portfolio manager) evaluates the debate and delivers a final verdict. This adversarial process catches blind spots that consensus misses.

### Phase 4: Memory & Learning (`memory_trader.py`)
```bash
python memory_trader.py NVDA
```
Phase 3 + persistent memory. Every decision is recorded, outcomes are tracked, and agent accuracy stats update over time. High-accuracy agents earn more influence in future decisions.

### Phase 5: Production (`prod_trader.py`)
```bash
python prod_trader.py NVDA
```
The full pipeline: Analysts → Debate → Risk Manager → Broker → Alerts → Memory. Includes position sizing, drawdown protection, and multi-channel notifications.

---

## 📡 24/7 Market Watcher

Continuous monitoring for crypto markets (Bitkub exchange):

```bash
# Single poll (for cron: */5 * * * *)
python watcher.py --tick

# Continuous daemon
python watcher.py --daemon

# Check status
python watcher.py --status

# Generate intraday summary for debate agents
python watcher.py --summary
```

**Detects:**
- Price spikes/drops (>3% in 1h, >5% in 4h)
- Volume surges (>2x rolling average)
- New 24h highs/lows

**Alerts via:** Console, file logs, Telegram

The watcher's **market context** is injected directly into Bull/Bear/Judge prompts, giving debate agents real-time awareness.

---

## 📊 Streamlit Dashboard

```bash
streamlit run dashboard.py
```

| Tab | What It Shows |
|-----|---------------|
| 🦈 **Trading Monitor** | Decision history, agent performance, portfolio summary, live analysis |
| 📡 **Market Watcher** | Live WebSocket prices, 1h candles, RSI chart, event log |
| 🤖 **LLM Usage** | API calls by provider, cost tracking, circuit breaker status, latency |
| 🏗️ **Architecture** | PowerFactory-style interactive diagram with real-time data flow |

---

## 💡 LLM Strategy: Smart & Cheap

We don't need GPT-4 prices. The system is designed for **cost efficiency**:

| Provider | Role | Cost |
|----------|------|------|
| **Gemini 2.5 Flash** | Primary (250 req/day free) | **$0** |
| **DeepSeek Chat** | Fallback | **$0.14/M tokens** |
| **Rule-based mode** | Zero-API fallback | **$0** |

**Circuit breaker:** After 2 consecutive failures on primary, automatically switches to fallback. No manual intervention needed.

---

## 📁 Project Structure

```
tradingagents_simple/
│
├── core/                           # Engine components
│   ├── agent.py                    # Base TradingAgent (rules + LLM modes)
│   ├── llm.py                      # Multi-provider LLM with circuit breaker
│   ├── data.py                     # yfinance data fetcher
│   ├── bitkub_client.py            # Bitkub REST API client
│   ├── bitkub_data.py              # Bitkub data adapter
│   ├── bitkub_ws.py                # WebSocket live price feed
│   ├── market_context.py           # Intraday context aggregator
│   ├── memory.py                   # Decision tracking + agent stats
│   ├── risk_manager.py             # Portfolio limits & veto power
│   ├── broker.py                   # Execution (dry/Alpaca/Bitkub)
│   ├── alerts.py                   # Notifications (console/file/Telegram)
│   ├── event_bus.py                # Real-time architecture monitoring
│   └── indicators.py               # Technical indicators
│
├── agents/                         # Specialist agents
│   ├── team.py                     # AgentTeam coordinator
│   ├── technical.py                # Technical analysis specialist
│   ├── fundamental.py              # Fundamental analysis specialist
│   ├── sentiment.py                # Sentiment analysis specialist
│   └── debate/                     # Adversarial reasoning engine
│       ├── orchestrator.py         # Debate flow controller
│       ├── bull.py                 # Bull researcher (argues BUY)
│       ├── bear.py                 # Bear researcher (argues SELL)
│       └── judge.py                # Portfolio manager (final verdict)
│
├── components/                     # Dashboard UI components
│   ├── architecture_canvas.py      # Interactive architecture diagram
│   └── demo_events.py              # Event pipeline demo
│
├── data/                           # Persistent storage
│   ├── trading_memory.json         # Decision history
│   ├── watchlist.json              # Monitored assets
│   ├── logs/                       # LLM calls, trades
│   └── watcher/                    # Market snapshots & events
│
├── tests/                          # Unit tests
├── docs/plans/                     # Architecture design documents
│
├── simple_trader.py                # Phase 1: Single agent
├── team_trader.py                  # Phase 2: Multi-agent team
├── debate_trader.py                # Phase 3: Bull vs Bear debate
├── memory_trader.py                # Phase 4: + Memory & learning
├── prod_trader.py                  # Phase 5: Full production
├── watcher.py                      # 24/7 market monitor
├── bitkub_trader.py                # Bitkub crypto trading
├── dashboard.py                    # Streamlit dashboard
└── config.py                       # All configuration
```

---

## ⚙️ Configuration

All settings live in `config.py`:

```python
# LLM Providers (switch with one line)
DEFAULT_CONFIG = GEMINI_CONFIG      # Free tier
FALLBACK_CONFIG = DEEPSEEK_CONFIG   # $0.14/M tokens

# Risk Management
RISK_CONFIG = {
    "confidence_threshold": 0.6,    # Min confidence to trade
    "max_position_size": 1000,      # Max $ per trade
    "max_positions": 5,             # Max concurrent positions
    "daily_loss_limit": 0.05,       # 5% daily circuit breaker
}

# Crypto (Bitkub)
CRYPTO_RISK_CONFIG = {
    "confidence_threshold": 0.65,   # Higher bar for volatile crypto
    "stop_loss_pct": 0.05,          # 5% stop loss
    "take_profit_pct": 0.10,        # 10% take profit
}

# Market Watcher
WATCHER_CONFIG = {
    "interval_seconds": 300,        # 5-min polling
    "price_alert_1h_pct": 3.0,     # Alert on 3%+ moves
    "telegram_alerts": True,        # Push notifications
}
```

---

## 🏭 System Architecture Board — DIgSILENT PowerFactory Style

> *Think German. Think scalable. Understand the whole system in one glance.*

Inspired by **DIgSILENT PowerFactory** — the gold standard for power system simulation used by engineers across Germany and Europe — our Architecture tab renders the entire trading pipeline as a **live, interactive single-line diagram (SLD)**.

### Why PowerFactory?

PowerFactory doesn't just *show* a power grid — it shows **power flowing through it in real time**. You see which nodes are active, which lines carry load, where bottlenecks form. One glance tells you the health of a 10,000-bus network.

We apply the same principle to our trading system:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   ┌──────────┐     ┌─────────────┐                                      │
│   │ MARKET   │────▶│ FUNDAMENTAL │──┐                                   │
│   │ DATA     │────▶│ TECHNICAL   │──┼──▶ DEBATE ──▶ RISK ──▶ BROKER    │
│   │ (Bitkub) │────▶│ SENTIMENT   │──┘   ENGINE     MGR                  │
│   └──────────┘     └─────────────┘                                      │
│        ▲                 ▲                                               │
│        │           ┌─────┴─────┐                                        │
│        └───────────│    LLM    │                                        │
│                    │ PROVIDER  │                                        │
│                    └───────────┘                                        │
│                                                                          │
│   ● = status dot (green/red)    ~~~▶ = particle flow (data moving)      │
│   [hover] = latency + status    [scroll] = zoom  [drag] = pan          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### What You See in Real Time

| Element | What It Means |
|---------|---------------|
| **Green particles** flowing along bezier curves | Data packets moving between components |
| **Status dots** on each node (green/red) | Component health — running, error, idle |
| **Signal labels** on connections (`price[]`, `score`, `decision`) | What data type flows through each link |
| **Latency overlay** on hover | How long each component takes to respond |
| **Node sub-blocks** | Internal capabilities (e.g. RSI, MACD, Bollinger inside Technical) |

### The German Engineering Mindset

The architecture board embodies three principles from German industrial software design:

**1. Übersichtlichkeit (Overview clarity)**
Every component, every connection, every data flow — visible on one screen. No hidden magic. No tabs to click. The entire system state is comprehensible at a glance, just like a PowerFactory SLD shows an entire power grid.

**2. Modularität (Modularity for scale)**
Each node is a self-contained block with defined inputs and outputs (terminals). Adding a new analyst? Drop a new node, connect its terminals. The architecture diagram literally shows you where to plug it in. This is how PowerFactory scales from a single generator to a national grid.

**3. Echtzeit-Überwachung (Real-time monitoring)**
Not a static diagram — a **living system view**. Particles spawn and flow. Status dots pulse. Latencies update. When you run a live analysis, you watch data flow from Market Data → Analysts → Debate → Risk → Broker in real time. When something fails, you see it turn red *immediately*.

### Under the Hood

The architecture board is built on three components:

| Component | File | Role |
|-----------|------|------|
| **EventBus** | `core/event_bus.py` | Thread-safe singleton, circular buffer (500 events), captures every system interaction |
| **Architecture Canvas** | `components/architecture_canvas.py` | Pure HTML5 Canvas renderer — bezier curves, particle system, pan/zoom, hover tooltips |
| **Demo Events** | `components/demo_events.py` | Simulates a full pipeline cycle (~20s) for visualization without live API calls |

```python
# How any component reports to the architecture board:
from core.event_bus import EventBus

bus = EventBus.instance()
bus.emit(
    source="technical",
    target="debate",
    signal="score",
    value=0.78,
    latency_ms=150,
    status="ok"
)
# → Instantly visible as a green particle flowing from Technical to Debate
```

### Interactive Controls

| Action | Effect |
|--------|--------|
| **Scroll wheel** | Zoom in/out (0.2x – 5x) toward cursor |
| **Click + drag** | Pan the entire diagram |
| **Hover a node** | Show status, latency, sub-components |
| **Zoom badge** (bottom-right) | Current zoom level |

### Demo Mode vs Live Mode

- **Demo Mode**: Click "Run Demo Pipeline" → watch simulated data flow through all stages with realistic latencies
- **Live Mode**: Run an actual analysis → the EventBus captures real events and the diagram shows actual data flowing in real time

---

## 🎯 Design Philosophy

### Why Debate > Consensus?

Traditional multi-agent systems take a **vote** — majority wins. The problem? Groupthink. If 2 out of 3 agents are bullish, the system buys — even if the one bearish agent spotted a critical risk.

Our **debate system** forces the bull to directly address bearish arguments and vice versa. The judge sees both sides **at their strongest**. This is how real trading desks avoid catastrophic blind spots.

### Why Progressive Phases?

Each phase is a complete, working system. You can run Phase 1 forever if that's all you need. But when you're ready for more sophistication, the next phase builds on top — no rewrites, just new layers.

### Why Memory Matters?

An agent that doesn't remember its mistakes is doomed to repeat them. Our memory system tracks:
- Every decision and its outcome
- Per-agent accuracy over time
- Which agents perform best in which market conditions

This turns the system into a **learning organism**, not just a decision engine.

### Why PowerFactory-Style Architecture?

Most AI systems are black boxes. You feed input, get output, and hope for the best. In power engineering, that approach would cause blackouts. PowerFactory shows every bus, every line, every transformer — because **you can't manage what you can't see**.

Our architecture board applies the same principle: **total system transparency**. Every LLM call, every analyst score, every risk decision — visible, traceable, debuggable. When something goes wrong, you don't grep logs. You *see* it on the board.

---

## 🔮 What's Next

- [ ] Backtest framework with historical replay
- [ ] Multi-ticker portfolio optimization
- [ ] Architecture board: historical replay mode (scrub timeline like PowerFactory simulation)
- [ ] Agent personality tuning based on market regime
- [ ] Cross-asset correlation awareness
- [ ] Architecture board: alarm system with node blinking on anomalies

---

**Built with Claude Code** 🤖 | Inspired by [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) & [DIgSILENT PowerFactory](https://www.digsilent.de/en/powerfactory.html)
