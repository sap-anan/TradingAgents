"""
Agent Team Manager - Coordinates specialist agents
Phase 2: Multi-agent collaboration with consensus decision
"""
from typing import Dict, Any, List
from core.llm import LLMInterface
from core.data import DataFetcher
from .technical import TechnicalAgent
from .fundamental import FundamentalAgent
from .sentiment import SentimentAgent


class AgentTeam:
    """
    Coordinates multiple specialist agents to produce a consensus decision.

    How it works:
    1. Each specialist analyzes independently (parallel in spirit)
    2. Views are collected: BULLISH / BEARISH / NEUTRAL
    3. A synthesis agent (or weighted vote) produces the final decision

    Extension points:
    - Phase 3: Add debate between bull/bear researchers
    - Phase 4: Add memory (learn which agents are most accurate)
    - Phase 5: Add risk manager for final approval
    """

    def __init__(self, llm: LLMInterface, data_fetcher: DataFetcher):
        self.llm = llm
        self.data = data_fetcher
        self.agents = [
            TechnicalAgent(llm),
            FundamentalAgent(llm),
            SentimentAgent(llm),
        ]

    def analyze_and_decide(self, ticker: str, date: str = None) -> Dict[str, Any]:
        """Run all agents and produce consensus decision"""
        print(f"\n{'='*50}")
        print(f"🏢 Agent Team Analyzing: {ticker}")
        print(f"{'='*50}")

        # Step 1: Fetch data (shared across all agents)
        print(f"\n📊 Fetching market data...")
        stock_data = self.data.fetch_stock_data(ticker, date)
        cs = stock_data.get("currency", "$")
        print(f"✓ {ticker} @ {cs}{stock_data['current_price']:,.2f}")

        # Step 2: Each specialist analyzes
        agent_views = []
        for agent in self.agents:
            print(f"\n{agent.ICON} {agent.ROLE} analyzing...")
            view = agent.analyze(stock_data)
            agent_views.append(view)
            print(f"  → {view['view']} ({view['confidence']:.0%}): {view['analysis'][:80]}...")

        # Step 3: Synthesize consensus
        print(f"\n🤝 Building consensus...")
        decision = self._synthesize(stock_data, agent_views)

        return {
            "ticker": ticker,
            "date": stock_data["date"],
            "current_price": stock_data["current_price"],
            "currency": stock_data.get("currency", "$"),
            "decision": decision["decision"],
            "confidence": decision["confidence"],
            "reasoning": decision["reasoning"],
            "agent_views": agent_views,
            "mode": "multi-agent",
            "data": stock_data,
        }

    def _synthesize(self, stock_data: Dict, views: List[Dict]) -> Dict[str, Any]:
        """
        Synthesize multiple agent views into a final decision.
        Uses LLM as a "senior trader" to weigh all perspectives.
        """
        views_text = "\n".join(
            f"- {v['agent']}: {v['view']} ({v['confidence']:.0%}) — {v['analysis']}"
            for v in views
        )

        prompt = f"""You are a Senior Trader making the FINAL trading decision for {stock_data['ticker']}.

## Current Price: {stock_data.get("currency", "$")}{stock_data['current_price']:,.2f}

## Analyst Team Views:
{views_text}

## Your Task
Weigh all analyst views and make the FINAL decision.
- If analysts mostly agree → follow consensus with high confidence
- If analysts disagree → lean conservative (HOLD) with lower confidence
- Consider which analyst's view is most relevant for current conditions

Respond in JSON:
{{"decision": "BUY" or "SELL" or "HOLD", "confidence": 0.0-1.0, "reasoning": "2-3 sentences explaining your final decision, referencing which analysts you agreed with and why"}}"""

        response = self.llm.chat(prompt)

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
                    "reasoning": parsed.get("reasoning", "Consensus reached"),
                }
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: weighted voting
        return self._weighted_vote(views)

    def _weighted_vote(self, views: List[Dict]) -> Dict[str, Any]:
        """Fallback: Simple weighted voting if LLM synthesis fails"""
        scores = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
        for v in views:
            scores[v["view"]] = scores.get(v["view"], 0) + v["confidence"]

        if scores["BULLISH"] > scores["BEARISH"] + 0.3:
            decision = "BUY"
        elif scores["BEARISH"] > scores["BULLISH"] + 0.3:
            decision = "SELL"
        else:
            decision = "HOLD"

        total = sum(scores.values())
        confidence = max(scores.values()) / total if total > 0 else 0.5

        return {
            "decision": decision,
            "confidence": round(confidence, 2),
            "reasoning": f"Vote: Bull {scores['BULLISH']:.1f} vs Bear {scores['BEARISH']:.1f} vs Neutral {scores['NEUTRAL']:.1f}",
        }
