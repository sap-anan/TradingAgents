# Simple Trading Agent - Phase 1

A **minimal but extensible** AI trading agent system. Start simple, extend to best-in-class.

## 🎯 What This Is

- **Phase 1** of a progressive agentic trading system
- Single agent that analyzes stocks and makes decisions
- Clean architecture with clear extension points
- Uses **DeepSeek** (ultra cheap: $0.14/M tokens)

## 🚀 Quick Start

```bash
cd /home/sap-anan/projects/TradingAgents/tradingagents_simple

# Test with NVDA
python simple_trader.py NVDA

# Test with specific date
python simple_trader.py AAPL --date 2024-01-15
```

## 📁 Project Structure

```
tradingagents_simple/
├── core/
│   ├── agent.py      # Trading agent (TODO: enhance analysis logic)
│   ├── data.py       # Data fetcher (extensible to new sources)
│   └── llm.py        # LLM interface (swappable providers)
├── simple_trader.py  # Main script
├── config.py         # Configuration (DeepSeek + Gemini)
└── README.md         # This file
```

## 🎓 Your Task

**Enhance the analysis logic** in `core/agent.py`:

1. Open: `core/agent.py`
2. Find: `def _analyze_stock(...)` method
3. Look for: `TODO(human)` comment
4. Improve: The simple decision logic

**Current logic** (placeholder):
- If price up 5%+ and RSI < 70 → BUY
- If RSI > 75 → SELL
- Otherwise → HOLD

**Your improvements** could include:
- Multi-factor analysis (combine RSI, SMA, volume, volatility)
- Weighted scoring system
- Sector-specific logic
- Risk-adjusted decisions
- Confidence calculation based on signal strength

## 🔧 Extension Paths

### Phase 2: Multi-Agent System

```python
class TechnicalAgent(TradingAgent):
    def _analyze_stock(self, data):
        # Focus only on technical indicators
        pass

class FundamentalAgent(TradingAgent):
    def _analyze_stock(self, data):
        # Focus on company financials
        pass

class AgentTeam:
    def __init__(self):
        self.technical = TechnicalAgent(...)
        self.fundamental = FundamentalAgent(...)

    def analyze(self, ticker):
        tech_decision = self.technical.analyze(ticker)
        fund_decision = self.fundamental.analyze(ticker)
        return self.synthesize([tech_decision, fund_decision])
```

### Phase 3: Add LLM Reasoning

```python
def _analyze_stock(self, stock_data):
    # Use LLM to analyze data
    prompt = self._build_analysis_prompt(stock_data)
    llm_response = self.llm.chat(prompt)
    decision = self._parse_llm_response(llm_response)
    return decision
```

### Phase 4: Add Memory & Learning

```python
class AdaptiveAgent(TradingAgent):
    def __init__(self, ...):
        super().__init__(...)
        self.memory = TradeMemory()

    def analyze(self, ticker):
        past_performance = self.memory.get_similar_trades(ticker)
        decision = super().analyze(ticker, context=past_performance)
        self.memory.store(ticker, decision)
        return decision
```

### Phase 5: Production Features

- Real-time data streams
- Broker API integration
- Portfolio management
- Risk engine
- Backtesting framework
- Performance monitoring

## ⚙️ Configuration

Edit `config.py` to change:

```python
# Switch LLM provider
DEFAULT_CONFIG = GEMINI_CONFIG  # Use free Gemini instead

# Adjust data parameters
DATA_CONFIG = {
    "lookback_days": 60,  # Look back 60 days instead of 30
}

# Change trading parameters
TRADING_CONFIG = {
    "confidence_threshold": 0.7,  # Higher confidence required
}
```

## 💡 Next Steps

1. **Improve analysis logic** (your TODO)
2. **Test on multiple stocks** (NVDA, AAPL, TSLA, etc.)
3. **Add new indicators** (MACD, Bollinger Bands, etc.)
4. **Extend to Phase 2** (multi-agent)
5. **Add LLM reasoning** (let AI analyze the data)

## 🎯 Goals

- ✅ **Works immediately** - Run it now, get results
- ✅ **Clean architecture** - Easy to understand and extend
- ✅ **Educational** - Learn by improving it
- ✅ **Extensible** - Clear path to sophisticated system
- ✅ **Cost-effective** - Uses cheapest LLM ($0.14/M tokens)

---

**Built with Claude Code** 🤖
