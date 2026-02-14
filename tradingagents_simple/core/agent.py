"""
Trading Agent - The decision maker
Single agent with clean extension points for multi-agent systems

Supports two analysis modes:
  1. Rule-based (fast, free, no API calls)
  2. LLM-powered (smart, uses DeepSeek/Gemini for reasoning)
"""
import json
import re
from typing import Dict, Any
from .llm import LLMInterface
from .data import DataFetcher


class TradingAgent:
    """
    Single-agent trading system with extensible architecture

    Extension paths:
    - Phase 2: Inherit → create SpecialistAgents (Technical, Fundamental, etc.)
    - Phase 3: Add AgentManager → coordinate multiple agents
    - Phase 4: Add Memory → learn from past trades
    - Phase 5: Add Broker → execute real trades
    """

    def __init__(self, llm: LLMInterface, data_fetcher: DataFetcher, mode: str = "llm"):
        """
        Args:
            llm: LLM interface for AI-powered analysis
            data_fetcher: Data source interface
            mode: "llm" (AI-powered) or "rules" (rule-based, no API calls)
        """
        self.llm = llm
        self.data = data_fetcher
        self.mode = mode

    def analyze_and_decide(self, ticker: str, date: str = None) -> Dict[str, Any]:
        """Main entry point: Analyze stock and make trading decision"""
        print(f"\n📊 Analyzing {ticker}...")

        # Step 1: Fetch market data
        stock_data = self.data.fetch_stock_data(ticker, date)
        cs = stock_data.get("currency", "$")
        print(f"✓ Data fetched: {cs}{stock_data['current_price']:.2f}")

        # Step 2: Analyze using selected mode
        if self.mode == "llm":
            print(f"🤖 AI analyzing with {self.llm.config.get('model', 'unknown')}...")
            analysis = self._llm_analyze(stock_data)
        else:
            print(f"📐 Rule-based analysis...")
            analysis = self._rule_based_analyze(stock_data)

        # Step 3: Package result
        return {
            "ticker": ticker,
            "date": stock_data["date"],
            "current_price": stock_data["current_price"],
            "decision": analysis["decision"],
            "confidence": analysis["confidence"],
            "reasoning": analysis["reasoning"],
            "mode": self.mode,
            "data": stock_data,
        }

    # =========================================================================
    # Mode 1: LLM-Powered Analysis (Smart, uses DeepSeek API)
    # =========================================================================

    def _llm_analyze(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM (DeepSeek/Gemini) to analyze stock data intelligently.
        The AI reasons about multiple factors and provides nuanced analysis.
        """
        prompt = self._build_analysis_prompt(stock_data)
        raw_response = self.llm.chat(prompt)
        return self._parse_llm_response(raw_response)

    def _build_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Build structured prompt for LLM analysis"""
        ind = data["indicators"]
        prices = data["history"]["prices"]
        cs = data.get("currency", "$")

        # Calculate additional context for LLM
        recent_5 = prices[-5:] if len(prices) >= 5 else prices
        trend_5d = ((recent_5[-1] - recent_5[0]) / recent_5[0] * 100) if len(recent_5) > 1 else 0

        rsi_str = f"{ind['rsi']:.1f}" if ind['rsi'] else "N/A"
        sma20_str = f"{cs}{ind['sma_20']:.2f}" if ind['sma_20'] else "N/A"
        sma50_str = f"{cs}{ind['sma_50']:.2f}" if ind['sma_50'] else "N/A"
        vol_str = f"{ind['volatility']:.2f}" if ind['volatility'] else "N/A"

        if ind['sma_20'] and data['current_price'] > ind['sma_20']:
            sma20_signal = "ABOVE (bullish)"
        elif ind['sma_20']:
            sma20_signal = "BELOW (bearish)"
        else:
            sma20_signal = "N/A"

        if ind['sma_50'] and data['current_price'] > ind['sma_50']:
            sma50_signal = "ABOVE (bullish)"
        elif ind['sma_50']:
            sma50_signal = "BELOW (bearish)"
        else:
            sma50_signal = "N/A"

        asset_type = "cryptocurrency" if cs == "฿" else "stock"
        return f"""You are an expert {asset_type} market analyst. Analyze this data and provide a trading decision.

## {'Coin' if cs == '฿' else 'Stock'}: {data['ticker']} ({data['info']['name']})
- Sector: {data['info']['sector']}
- Current Price: {cs}{data['current_price']:,.2f}
- Date: {data['date']}

## Technical Indicators
- 30-day Price Change: {ind['price_change_pct']:.2f}%
- 5-day Trend: {trend_5d:.2f}%
- RSI (14): {rsi_str}
- SMA 20: {sma20_str}
- SMA 50: {sma50_str}
- Volatility: {vol_str}% daily
- Volume: {data['volume']:,}

## Price vs Moving Averages
- Price vs SMA20: {sma20_signal}
- Price vs SMA50: {sma50_signal}

## Recent Price History (last 10 days)
{self._format_recent_prices(data['history'], cs)}

## Your Task
Analyze ALL the data above and provide your trading decision.

You MUST respond in EXACTLY this JSON format (no other text):
{{
    "decision": "BUY" or "SELL" or "HOLD",
    "confidence": 0.0 to 1.0,
    "reasoning": "2-3 sentence explanation covering: trend analysis, indicator signals, and risk factors"
}}"""

    def _format_recent_prices(self, history: Dict, currency: str = "$") -> str:
        """Format recent price history for prompt"""
        prices = history["prices"][-10:]
        dates = history["dates"][-10:]
        lines = []
        for d, p in zip(dates, prices):
            lines.append(f"  {d}: {currency}{p:,.2f}")
        return "\n".join(lines)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured decision"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*"decision"[^{}]*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                decision = parsed.get("decision", "HOLD").upper()
                if decision not in ("BUY", "SELL", "HOLD"):
                    decision = "HOLD"
                return {
                    "decision": decision,
                    "confidence": min(1.0, max(0.0, float(parsed.get("confidence", 0.5)))),
                    "reasoning": parsed.get("reasoning", "AI analysis completed"),
                }
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: extract decision from text
        response_upper = response.upper()
        if "BUY" in response_upper and "SELL" not in response_upper:
            decision = "BUY"
        elif "SELL" in response_upper and "BUY" not in response_upper:
            decision = "SELL"
        else:
            decision = "HOLD"

        return {
            "decision": decision,
            "confidence": 0.5,
            "reasoning": response[:200] if response else "AI analysis completed",
        }

    # =========================================================================
    # Mode 2: Rule-Based Analysis (Fast, Free, No API calls)
    # =========================================================================

    def _rule_based_analyze(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Multi-factor scoring system for trading decisions.
        No API calls needed - pure math and logic.

        TODO(human): Enhance this scoring system with your own trading insights!
        Consider adding:
        - MACD crossover signals
        - Bollinger Band analysis
        - Volume-weighted scoring
        - Sector-specific adjustments
        """
        indicators = stock_data["indicators"]
        current_price = stock_data["current_price"]

        # Extract indicators
        rsi = indicators.get("rsi")
        sma_20 = indicators.get("sma_20")
        sma_50 = indicators.get("sma_50")
        price_change = indicators.get("price_change_pct", 0)
        volatility = indicators.get("volatility", 0)

        # Multi-factor scoring: -10 (strong sell) to +10 (strong buy)
        score = 0
        signals = []

        # Factor 1: Price trend (30-day)
        if price_change > 10:
            score += 3
            signals.append(f"Strong uptrend +{price_change:.1f}%")
        elif price_change > 3:
            score += 2
            signals.append(f"Moderate uptrend +{price_change:.1f}%")
        elif price_change > 0:
            score += 1
            signals.append(f"Slight uptrend +{price_change:.1f}%")
        elif price_change > -5:
            score -= 1
            signals.append(f"Slight downtrend {price_change:.1f}%")
        else:
            score -= 3
            signals.append(f"Strong downtrend {price_change:.1f}%")

        # Factor 2: RSI momentum
        if rsi:
            if rsi < 30:
                score += 2
                signals.append(f"Oversold RSI {rsi:.0f} (buy opportunity)")
            elif rsi < 45:
                score += 1
                signals.append(f"Low RSI {rsi:.0f} (potential upside)")
            elif rsi > 75:
                score -= 3
                signals.append(f"Overbought RSI {rsi:.0f} (sell signal)")
            elif rsi > 65:
                score -= 1
                signals.append(f"High RSI {rsi:.0f} (caution)")
            else:
                signals.append(f"Neutral RSI {rsi:.0f}")

        # Factor 3: Price vs SMA20 (short-term trend)
        if sma_20:
            if current_price > sma_20 * 1.03:
                score += 2
                signals.append(f"Price well above SMA20 (bullish)")
            elif current_price > sma_20:
                score += 1
                signals.append(f"Price above SMA20")
            elif current_price < sma_20 * 0.97:
                score -= 2
                signals.append(f"Price well below SMA20 (bearish)")
            else:
                score -= 1
                signals.append(f"Price below SMA20")

        # Factor 4: Volatility risk adjustment
        if volatility:
            if volatility > 4:
                score -= 1
                signals.append(f"High volatility {volatility:.1f}% (risky)")
            elif volatility < 1:
                signals.append(f"Low volatility {volatility:.1f}% (stable)")

        # Convert score to decision
        if score >= 4:
            decision = "BUY"
            confidence = min(0.95, 0.6 + score * 0.05)
        elif score >= 2:
            decision = "BUY"
            confidence = 0.55 + score * 0.03
        elif score <= -4:
            decision = "SELL"
            confidence = min(0.95, 0.6 + abs(score) * 0.05)
        elif score <= -2:
            decision = "SELL"
            confidence = 0.55 + abs(score) * 0.03
        else:
            decision = "HOLD"
            confidence = 0.4 + abs(score) * 0.05

        reasoning = " | ".join(signals[:4])

        return {
            "decision": decision,
            "confidence": round(confidence, 2),
            "reasoning": f"Score: {score}/10 — {reasoning}",
        }
