"""
Technical Analyst Agent
Specializes in price patterns, indicators, and chart analysis
"""
from typing import Dict, Any
from core.llm import LLMInterface


class TechnicalAgent:
    """Expert in technical analysis: RSI, SMA, MACD, volume patterns"""

    ROLE = "Technical Analyst"
    ICON = "📊"

    def __init__(self, llm: LLMInterface):
        self.llm = llm

    def analyze(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze stock using technical indicators only"""
        prompt = self._build_prompt(stock_data)
        response = self.llm.chat(prompt)
        return self._parse_response(response)

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        ind = data["indicators"]
        prices = data["history"]["prices"]

        recent_5 = prices[-5:] if len(prices) >= 5 else prices
        trend_5d = ((recent_5[-1] - recent_5[0]) / recent_5[0] * 100) if len(recent_5) > 1 else 0

        # Price momentum analysis
        recent_10 = prices[-10:] if len(prices) >= 10 else prices
        higher_highs = sum(1 for i in range(1, len(recent_10)) if recent_10[i] > recent_10[i-1])
        trend_strength = higher_highs / max(len(recent_10) - 1, 1) * 100

        cs = data.get("currency", "$")
        rsi_str = f"{ind['rsi']:.1f}" if ind['rsi'] else "N/A"
        sma20_str = f"{cs}{ind['sma_20']:,.2f}" if ind['sma_20'] else "N/A"

        return f"""You are a senior Technical Analyst. Focus ONLY on price action and technical indicators.

## {data['ticker']} Technical Data
- Price: {cs}{data['current_price']:,.2f}
- 30-day Change: {ind['price_change_pct']:.2f}%
- 5-day Trend: {trend_5d:.2f}%
- Trend Strength: {trend_strength:.0f}% of last 10 days were up days
- RSI (14): {rsi_str}
- SMA 20: {sma20_str}
- Volatility: {ind['volatility']:.2f}% daily
- Volume: {data['volume']:,}

## Recent Prices (last 10 days)
{chr(10).join(f"  {d}: {cs}{p:,.2f}" for d, p in zip(data['history']['dates'][-10:], prices[-10:]))}

## Your Analysis
As a Technical Analyst, evaluate:
1. Trend direction and strength
2. RSI momentum signals
3. Price vs moving averages
4. Volume confirmation
5. Key support/resistance levels

Respond in JSON:
{{"view": "BULLISH" or "BEARISH" or "NEUTRAL", "confidence": 0.0-1.0, "analysis": "2-3 sentences on technical outlook"}}"""

    def _parse_response(self, response: str) -> Dict[str, Any]:
        import json, re
        try:
            match = re.search(r'\{[^{}]*"view"[^{}]*\}', response, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                return {
                    "agent": self.ROLE,
                    "view": parsed.get("view", "NEUTRAL").upper(),
                    "confidence": min(1.0, max(0.0, float(parsed.get("confidence", 0.5)))),
                    "analysis": parsed.get("analysis", "Technical analysis completed"),
                }
        except (json.JSONDecodeError, ValueError):
            pass

        return {"agent": self.ROLE, "view": "NEUTRAL", "confidence": 0.5, "analysis": response[:200]}
