"""
Fundamental Analyst Agent
Specializes in company financials, valuation, and business health
"""
from typing import Dict, Any
from core.llm import LLMInterface


class FundamentalAgent:
    """Expert in fundamental analysis: financials, valuation, sector analysis"""

    ROLE = "Fundamental Analyst"
    ICON = "💼"

    def __init__(self, llm: LLMInterface):
        self.llm = llm

    def analyze(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze stock using fundamental data"""
        prompt = self._build_prompt(stock_data)
        response = self.llm.chat(prompt)
        return self._parse_response(response)

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        info = data["info"]
        mc = info.get("market_cap", 0)
        cs = data.get("currency", "$")
        mc_str = f"{cs}{mc/1e9:.1f}B" if mc > 1e9 else f"{cs}{mc/1e6:.0f}M" if mc > 1e6 else "N/A"

        return f"""You are a senior Fundamental Analyst. Focus on {'project health and tokenomics' if cs == '฿' else 'company health and valuation'}.

## {data['ticker']} ({info['name']}) Fundamentals
- Sector: {info['sector']}
- Market Cap: {mc_str}
- Current Price: {cs}{data['current_price']:,.2f}
- 30-day Price Change: {data['indicators']['price_change_pct']:.2f}%

## Your Analysis
As a Fundamental Analyst, evaluate:
1. Is the company in a strong sector?
2. Is the market cap reasonable for this price?
3. Based on the sector and recent price action, is the stock fairly valued?
4. What fundamental risks exist?

Note: You have limited fundamental data in this Phase 1 system.
Use your knowledge of {data['ticker']} to provide fundamental context.

Respond in JSON:
{{"view": "BULLISH" or "BEARISH" or "NEUTRAL", "confidence": 0.0-1.0, "analysis": "2-3 sentences on fundamental outlook"}}"""

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
                    "analysis": parsed.get("analysis", "Fundamental analysis completed"),
                }
        except (json.JSONDecodeError, ValueError):
            pass

        return {"agent": self.ROLE, "view": "NEUTRAL", "confidence": 0.5, "analysis": response[:200]}
