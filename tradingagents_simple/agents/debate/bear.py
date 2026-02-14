"""
Bear Researcher - Argues the case AGAINST buying
Finds every reason to be cautious or sell the stock
"""
from typing import Dict, Any, List
from core.llm import LLMInterface


class BearResearcher:
    """Argues the bearish case - looks for reasons to SELL or avoid"""

    ROLE = "Bear Researcher"
    ICON = "🐻"

    def __init__(self, llm: LLMInterface):
        self.llm = llm

    def make_case(self, stock_data: Dict, analyst_views: List[Dict],
                  bull_argument: str = None, round_num: int = 1) -> Dict[str, Any]:
        """Build the bearish argument, optionally rebutting the bull"""
        prompt = self._build_prompt(stock_data, analyst_views, bull_argument, round_num)
        response = self.llm.chat(prompt)
        return self._parse(response)

    def _build_prompt(self, data: Dict, views: List[Dict],
                      bull_arg: str, round_num: int) -> str:
        views_text = "\n".join(f"  - {v['agent']}: {v['view']} — {v['analysis']}" for v in views)

        rsi = data['indicators']['rsi']
        rsi_str = f"{rsi:.1f}" if rsi else "N/A"

        rebuttal = ""
        if bull_arg:
            rebuttal = f"""
## Bull's Argument (Round {round_num - 1})
{bull_arg}

You MUST directly address and counter the bull's specific points above.
"""

        return f"""You are the BEAR RESEARCHER for {data['ticker']}. Your job is to argue why this stock should NOT be bought (or should be SOLD).

## Stock: {data['ticker']} @ {data.get("currency", "$")}{data['current_price']:,.2f}
- 30-day Change: {data['indicators']['price_change_pct']:.2f}%
- RSI: {rsi_str}
- Company: {data['info']['name']} ({data['info']['sector']})

## Analyst Team Reports
{views_text}
{rebuttal}
## Your Task (Round {round_num})
Make the STRONGEST possible case AGAINST buying {data['ticker']}.
- Find bearish signals and risks the analysts might have missed
- Highlight overvaluation, momentum loss, or sector headwinds
- If countering the bull, address their points directly
- Be persuasive but honest — don't fabricate data

Respond in JSON:
{{"argument": "Your 3-4 sentence bearish argument", "key_points": ["point1", "point2", "point3"], "conviction": 0.0-1.0}}"""

    def _parse(self, response: str) -> Dict[str, Any]:
        import json, re
        try:
            match = re.search(r'\{[^{}]*"argument"[^{}]*\}', response, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                return {
                    "role": self.ROLE,
                    "argument": parsed.get("argument", ""),
                    "key_points": parsed.get("key_points", []),
                    "conviction": min(1.0, max(0.0, float(parsed.get("conviction", 0.7)))),
                }
        except (json.JSONDecodeError, ValueError):
            pass
        return {"role": self.ROLE, "argument": response[:300], "key_points": [], "conviction": 0.5}
