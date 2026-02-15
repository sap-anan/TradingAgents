"""
Multi-Provider Configuration for TradingAgents
Supports: Google Gemini, XAI, DeepSeek, Kimi (Moonshot AI)
"""
import os
from tradingagents.default_config import DEFAULT_CONFIG

# ============================================================================
# Configuration 1: Google Gemini (FREE - Recommended for learning)
# ============================================================================
GEMINI_CONFIG = DEFAULT_CONFIG.copy()
GEMINI_CONFIG.update({
    "llm_provider": "google",
    "deep_think_llm": "gemini-2.0-flash-exp",      # Fast, free
    "quick_think_llm": "gemini-2.0-flash-exp",     # Same model for both
    "max_debate_rounds": 1,                         # Keep costs low
    "max_risk_discuss_rounds": 1,
})

# ============================================================================
# Configuration 2: XAI (Grok) - Native support
# ============================================================================
XAI_CONFIG = DEFAULT_CONFIG.copy()
XAI_CONFIG.update({
    "llm_provider": "xai",
    "deep_think_llm": "grok-beta",
    "quick_think_llm": "grok-beta",
    "max_debate_rounds": 1,
})

# ============================================================================
# Configuration 3: DeepSeek (ULTRA CHEAP - $0.14/1M tokens)
# ============================================================================
DEEPSEEK_CONFIG = DEFAULT_CONFIG.copy()
DEEPSEEK_CONFIG.update({
    "llm_provider": "openai",  # Use OpenAI-compatible API
    "deep_think_llm": "deepseek-reasoner",         # Best reasoning model
    "quick_think_llm": "deepseek-chat",            # Fast chat model
    "backend_url": "https://api.deepseek.com",     # DeepSeek API endpoint
    "max_debate_rounds": 2,  # Can afford more rounds!
})
# Note: Set OPENAI_API_KEY=your_deepseek_key in .env (DeepSeek uses OpenAI format)

# ============================================================================
# Configuration 4: Kimi (Moonshot AI) - Chinese, Good Quality
# ============================================================================
KIMI_CONFIG = DEFAULT_CONFIG.copy()
KIMI_CONFIG.update({
    "llm_provider": "openai",  # Use OpenAI-compatible API
    "deep_think_llm": "moonshot-v1-128k",          # 128K context
    "quick_think_llm": "moonshot-v1-8k",           # 8K context (faster)
    "backend_url": "https://api.moonshot.cn/v1",   # Kimi API endpoint
    "max_debate_rounds": 2,
})
# Note: Set OPENAI_API_KEY=your_kimi_key in .env (Kimi uses OpenAI format)

# ============================================================================
# Configuration 5: HYBRID (Smart cost optimization)
# ============================================================================
HYBRID_CONFIG = DEFAULT_CONFIG.copy()
HYBRID_CONFIG.update({
    # Use Gemini (free) for quick tasks, DeepSeek for deep thinking
    "llm_provider": "google",
    "deep_think_llm": "gemini-2.0-flash-exp",   # Free for complex reasoning
    "quick_think_llm": "gemini-2.0-flash-exp",  # Free for simple tasks
    "max_debate_rounds": 1,
})

# ============================================================================
# Usage Examples
# ============================================================================
if __name__ == "__main__":
    print("Available Configurations:")
    print("1. GEMINI_CONFIG   - Google Gemini (FREE)")
    print("2. XAI_CONFIG      - xAI Grok")
    print("3. DEEPSEEK_CONFIG - DeepSeek (Ultra cheap)")
    print("4. KIMI_CONFIG     - Kimi/Moonshot AI")
    print("5. HYBRID_CONFIG   - Mix of providers")
    print("\nCost comparison (per 1M tokens):")
    print("  Gemini:   $0.00 (free tier)")
    print("  DeepSeek: $0.14")
    print("  Kimi:     ~$0.50")
    print("  xAI Grok: ~$2.00")
    print("  GPT-4:    ~$10.00")
