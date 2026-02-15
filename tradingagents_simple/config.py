"""
Configuration for Simple Trading Agent
Optimized for FREE/CHEAPEST models
"""
import os
from dotenv import load_dotenv

load_dotenv()

# DeepSeek Configuration (ULTRA CHEAP - $0.14 per million tokens!)
DEEPSEEK_CONFIG = {
    "provider": "deepseek",
    "api_key": os.getenv("DEEPSEEK_API_KEY"),
    "base_url": "https://api.deepseek.com",

    # Model selection (DeepSeek R1 Distill Llama 70B = CHEAPEST)
    "model": "deepseek-chat",  # $0.14 per 1M tokens (input) + $0.28 output

    # Alternative models:
    # "deepseek-reasoner" - Better for complex reasoning ($0.55/$2.19 per 1M)
    # "deepseek-chat" - Best balance (cheap + good quality)
}

# Google Gemini Configuration (FREE)
GEMINI_CONFIG = {
    "provider": "google",
    "api_key": os.getenv("GOOGLE_API_KEY"),
    "model": "gemini-2.5-flash",  # FREE tier: 250 requests/day
}

# Default: Gemini (FREE) primary, DeepSeek (cheap) fallback
DEFAULT_CONFIG = GEMINI_CONFIG
FALLBACK_CONFIG = DEEPSEEK_CONFIG

# Data configuration
DATA_CONFIG = {
    "source": "yfinance",  # Free data source
    "lookback_days": 30,   # How many days of history
    "cache_enabled": True, # Cache data to avoid re-fetching
}

# Trading parameters
TRADING_CONFIG = {
    "confidence_threshold": 0.6,  # Minimum confidence to trade
    "max_position_size": 1000,     # Max $ per trade
    "risk_per_trade": 0.02,        # 2% risk per trade
}

# Risk Manager (Phase 5)
RISK_CONFIG = {
    "confidence_threshold": 0.6,
    "max_position_size": 1000,
    "max_positions": 5,
    "risk_per_trade": 0.02,
    "daily_loss_limit": 0.05,
    "portfolio_value": 10000,
}

# Broker (Phase 5)
BROKER_CONFIG = {
    "mode": "dry_run",  # "dry_run", "alpaca_paper", "alpaca_live"
    "api_key": os.getenv("ALPACA_API_KEY"),
    "secret_key": os.getenv("ALPACA_SECRET_KEY"),
}

# Bitkub (Thai Crypto Exchange)
BITKUB_CONFIG = {
    "api_key": os.getenv("BITKUB_API_KEY"),
    "api_secret": os.getenv("BITKUB_API_SECRET"),
}

# Bitkub Data Config
BITKUB_DATA_CONFIG = {
    "source": "bitkub",
    "lookback_days": 30,
    "candle_resolution": "60",  # 1h candles (1, 5, 15, 60, 240, 1D)
}

# Risk Config for Crypto (higher volatility, THB currency)
CRYPTO_RISK_CONFIG = {
    "confidence_threshold": 0.65,     # Higher bar — crypto is noisy
    "max_position_size": 5000,        # THB per trade
    "max_positions": 3,               # Fewer concurrent — concentration risk
    "risk_per_trade": 0.015,          # 1.5% of portfolio per trade
    "daily_loss_limit": 0.05,         # 5% daily circuit breaker
    "portfolio_value": 50000,         # THB starting capital
    "currency": "THB",
    # Crypto-specific
    "stop_loss_pct": 0.05,            # 5% stop loss (crypto swings wider)
    "take_profit_pct": 0.10,          # 10% take profit (2:1 reward:risk)
    "volatility_scale": True,         # Reduce size when volatility > 5%
}

# Market Watcher (24/7 monitoring)
WATCHER_CONFIG = {
    "interval_seconds": 300,           # 5 min polling
    "price_alert_1h_pct": 3.0,        # Alert if price changes >3% in 1 hour
    "price_alert_4h_pct": 5.0,        # Alert if price changes >5% in 4 hours
    "volume_spike_multiplier": 2.0,    # Alert if volume > 2x rolling average
    "retention_days": 30,              # Keep snapshots for 30 days
    "telegram_alerts": True,           # Send Telegram on significant events
    "data_dir": os.path.join(os.path.dirname(__file__), "data", "watcher"),
}

# Alerts (Phase 5)
ALERT_CONFIG = {
    "channels": ["console", "file"],  # Add "telegram" if configured
    "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN"),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
}
