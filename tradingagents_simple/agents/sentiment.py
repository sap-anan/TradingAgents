"""
Sentiment Analyst Agent
Specializes in market sentiment, news impact, and social mood
"""
from typing import Dict, Any
from core.llm import LLMInterface


class SentimentAgent:
    """Expert in market sentiment: news, social media, market mood"""

    ROLE = "Sentiment Analyst"
    ICON = "🎭"

    def __init__(self, llm: LLMInterface):
        self.llm = llm

    def analyze(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze stock sentiment"""
        prompt = self._build_prompt(stock_data)
        response = self.llm.chat(prompt)
        return self._parse_response(response)

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        prices = data["history"]["prices"]
        volumes = data["history"]["volumes"]

        # Volume trend (rising volume = strong sentiment)
        recent_vol = volumes[-5:] if len(volumes) >= 5 else volumes
        avg_vol = sum(volumes) / len(volumes) if volumes else 0
        recent_avg_vol = sum(recent_vol) / len(recent_vol) if recent_vol else 0
        vol_change = ((recent_avg_vol - avg_vol) / avg_vol * 100) if avg_vol > 0 else 0

        rsi = data['indicators']['rsi']
        rsi_str = f"{rsi:.1f}" if rsi else "N/A"
        rsi_zone = ""
        if rsi and rsi < 30:
            rsi_zone = "(fear zone)"
        elif rsi and rsi > 70:
            rsi_zone = "(greed zone)"

        if vol_change > 10:
            vol_label = "(increasing interest)"
        elif vol_change < -10:
            vol_label = "(decreasing interest)"
        else:
            vol_label = "(stable)"

        return f"""You are a Sentiment Analyst. Focus on market mood and social sentiment.

## {data['ticker']} ({data['info']['name']}) Sentiment Context
- Sector: {data['info']['sector']}
- Price: {data.get("currency", "$")}{data['current_price']:,.2f}
- 30-day Change: {data['indicators']['price_change_pct']:.2f}%
- Recent Volume vs Average: {vol_change:+.1f}% {vol_label}
- RSI: {rsi_str} {rsi_zone}

## Your Analysis
As a Sentiment Analyst, evaluate:
1. What is the current market mood for {data['ticker']}?
2. Is volume confirming or diverging from price action?
3. Based on your knowledge, any recent news/events affecting sentiment?
4. Is there fear (buy opportunity) or greed (sell signal)?

Respond in JSON:
{{"view": "BULLISH" or "BEARISH" or "NEUTRAL", "confidence": 0.0-1.0, "analysis": "2-3 sentences on sentiment outlook"}}"""

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
                    "analysis": parsed.get("analysis", "Sentiment analysis completed"),
                }
        except (json.JSONDecodeError, ValueError):
            pass

        return {"agent": self.ROLE, "view": "NEUTRAL", "confidence": 0.5, "analysis": response[:200]}
