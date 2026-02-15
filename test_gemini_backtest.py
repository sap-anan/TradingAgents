"""
First Backtest Test - Using Free Gemini API
This will run a simple trading decision for NVDA stock
"""
import os
from dotenv import load_dotenv
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# Load API keys from .env
load_dotenv()

# Configure for Gemini Free Tier (inherit from DEFAULT_CONFIG)
GEMINI_CONFIG = DEFAULT_CONFIG.copy()
GEMINI_CONFIG.update({
    "llm_provider": "google",
    "deep_think_llm": "gemini-2.5-flash",          # Free tier model (250 req/day)
    "quick_think_llm": "gemini-2.5-flash",         # Same model
    "max_debate_rounds": 1,                         # Keep it simple (save API calls)
    "max_risk_discuss_rounds": 1,
})

print("=" * 60)
print("🚀 TradingAgents First Backtest")
print("=" * 60)
print(f"Provider: Google Gemini (FREE)")
print(f"Stock: NVDA")
print(f"Date: 2024-01-15")
print("=" * 60)

try:
    # Initialize TradingAgents
    print("\n📊 Initializing TradingAgents...")
    ta = TradingAgentsGraph(debug=True, config=GEMINI_CONFIG)

    # Run backtest on NVDA
    print("\n🤖 Running multi-agent analysis...")
    print("This will take 2-5 minutes as agents discuss...\n")

    state, decision = ta.propagate("NVDA", "2024-01-15")

    # Display results
    print("\n" + "=" * 60)
    print("✅ BACKTEST COMPLETE!")
    print("=" * 60)
    print(f"\n📈 Final Decision: {decision}")
    print("\n💡 What happened:")
    print("  1. Analysts gathered data (fundamentals, news, technical)")
    print("  2. Researchers debated (bullish vs bearish)")
    print("  3. Trader made decision based on analysis")
    print("  4. Risk manager evaluated the trade")
    print("  5. Portfolio manager approved/rejected")
    print("\n" + "=" * 60)

except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nTroubleshooting:")
    print("  1. Check your GOOGLE_API_KEY in .env")
    print("  2. Ensure you have internet connection")
    print("  3. Verify the API key is valid at https://aistudio.google.com/")
    import traceback
    traceback.print_exc()
