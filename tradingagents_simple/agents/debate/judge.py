"""
Debate Judge - Evaluates bull vs bear arguments
Makes the final trading decision based on the debate
"""
from typing import Dict, Any, List
from core.llm import LLMInterface


class DebateJudge:
    """
    Evaluates the bull vs bear debate and renders final verdict.
    Acts as a senior portfolio manager who weighs both sides.
    """

    ROLE = "Portfolio Manager"
    ICON = "⚖️"

    def __init__(self, llm: LLMInterface):
        self.llm = llm

    def judge(self, stock_data: Dict, analyst_views: List[Dict],
              debate_rounds: List[Dict]) -> Dict[str, Any]:
        """Evaluate the full debate and make final decision"""
        prompt = self._build_prompt(stock_data, analyst_views, debate_rounds)
        response = self.llm.chat(prompt)
        return self._parse(response)

    def _build_prompt(self, data: Dict, views: List[Dict],
                      rounds: List[Dict]) -> str:
        views_text = "\n".join(f"  - {v['agent']}: {v['view']} ({v['confidence']:.0%})" for v in views)

        debate_text = ""
        for i, rnd in enumerate(rounds, 1):
            debate_text += f"\n### Round {i}\n"
            debate_text += f"🐂 BULL (conviction {rnd['bull']['conviction']:.0%}): {rnd['bull']['argument']}\n"
            debate_text += f"🐻 BEAR (conviction {rnd['bear']['conviction']:.0%}): {rnd['bear']['argument']}\n"

        market_ctx = ""
        if data.get("market_context"):
            market_ctx = f"\n## Intraday Market Context\n{data['market_context']}\n"

        return f"""You are a Senior Portfolio Manager making the FINAL trading decision.

## Stock: {data['ticker']} @ {data.get("currency", "$")}{data['current_price']:,.2f}
{market_ctx}
## Analyst Consensus
{views_text}

## Bull vs Bear Debate
{debate_text}

## Your Task
You have heard both sides. Now make your FINAL decision:

1. Who made the stronger argument — Bull or Bear?
2. Which specific points were most convincing?
3. What is the risk/reward balance?
4. What is your FINAL DECISION?

Rules:
- If Bull won convincingly → BUY
- If Bear won convincingly → SELL
- If debate was close or inconclusive → HOLD
- Higher conviction from the winning side = higher confidence

Respond in JSON:
{{"decision": "BUY" or "SELL" or "HOLD", "confidence": 0.0-1.0, "winner": "bull" or "bear" or "tie", "reasoning": "3-4 sentences explaining your verdict, referencing specific debate points"}}"""

    def _parse(self, response: str) -> Dict[str, Any]:
        import json, re
        try:
            match = re.search(r'\{[^{}]*"decision"[^{}]*\}', response, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                decision = parsed.get("decision", "HOLD").upper()
                if decision not in ("BUY", "SELL", "HOLD"):
                    decision = "HOLD"
                return {
                    "decision": decision,
                    "confidence": min(1.0, max(0.0, float(parsed.get("confidence", 0.5)))),
                    "winner": parsed.get("winner", "tie"),
                    "reasoning": parsed.get("reasoning", "Verdict rendered"),
                }
        except (json.JSONDecodeError, ValueError):
            pass
        return {"decision": "HOLD", "confidence": 0.5, "winner": "tie", "reasoning": response[:200]}
