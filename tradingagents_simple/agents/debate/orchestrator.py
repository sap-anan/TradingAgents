"""
Debate Orchestrator - Runs the multi-round Bull vs Bear debate
Phase 3: Analysts inform → Bull argues → Bear rebuts → repeat → Judge decides
"""
from typing import Dict, Any, List
from core.llm import LLMInterface
from core.data import DataFetcher
from core.market_context import MarketContext
from core.event_bus import EventBus
from agents.team import AgentTeam
from .bull import BullResearcher
from .bear import BearResearcher
from .judge import DebateJudge


class DebateOrchestrator:
    """
    Runs a structured debate between Bull and Bear researchers,
    informed by the Phase 2 analyst team, judged by a portfolio manager.

    Flow per ticker:
    1. Analyst team produces views (Technical, Fundamental, Sentiment)
    2. Bull makes opening argument
    3. Bear rebuts Bull
    4. Bull rebuts Bear (repeat for N rounds)
    5. Judge evaluates all rounds and renders verdict
    """

    def __init__(self, llm: LLMInterface, data_fetcher: DataFetcher,
                 num_rounds: int = 2):
        self.llm = llm
        self.data = data_fetcher
        self.num_rounds = max(1, min(num_rounds, 5))
        self.team = AgentTeam(llm, data_fetcher)
        self.bull = BullResearcher(llm)
        self.bear = BearResearcher(llm)
        self.judge = DebateJudge(llm)

    def analyze_and_decide(self, ticker: str, date: str = None) -> Dict[str, Any]:
        """Full debate pipeline for a single ticker"""
        # Phase 2: Analyst team analyzes
        team_result = self.team.analyze_and_decide(ticker, date)
        stock_data = team_result["data"]
        analyst_views = team_result["agent_views"]
        EventBus.instance().emit("team", "debate", "analyst_views", len(analyst_views), status="running")

        # Inject intraday market context (from watcher)
        market_context = MarketContext.context_string(date)
        if market_context:
            stock_data["market_context"] = market_context
            print(f"\n  📊 Market context loaded ({MarketContext.load_today(date).get('snapshot_count', 0)} ticks)")

        # Phase 3: Debate
        print(f"\n{'─'*50}")
        print(f"⚔️  Bull vs Bear Debate ({self.num_rounds} rounds)")
        print(f"{'─'*50}")

        debate_rounds = []
        bear_arg = None

        for rnd in range(1, self.num_rounds + 1):
            print(f"\n── Round {rnd} ──")

            # Bull argues (rebuts bear if not round 1)
            print(f"  🐂 Bull arguing...")
            bull_result = self.bull.make_case(
                stock_data, analyst_views, bear_argument=bear_arg, round_num=rnd
            )
            print(f"     Conviction: {bull_result['conviction']:.0%}")
            EventBus.instance().emit("debate", "debate", "bull_round", bull_result.get("conviction", 0), status="running")

            # Bear rebuts bull
            print(f"  🐻 Bear rebutting...")
            bear_result = self.bear.make_case(
                stock_data, analyst_views, bull_argument=bull_result["argument"], round_num=rnd
            )
            print(f"     Conviction: {bear_result['conviction']:.0%}")
            EventBus.instance().emit("debate", "debate", "bear_round", bear_result.get("conviction", 0), status="running")

            bear_arg = bear_result["argument"]
            debate_rounds.append({"bull": bull_result, "bear": bear_result})

        # Judge renders verdict
        print(f"\n  ⚖️  Judge deliberating...")
        verdict = self.judge.judge(stock_data, analyst_views, debate_rounds)
        print(f"     Winner: {verdict['winner'].upper()} → {verdict['decision']}")
        EventBus.instance().emit("debate", "risk_manager", "decision",
            {"signal": verdict.get("decision"), "confidence": verdict.get("confidence", 0)},
            status="running")

        return {
            "ticker": ticker,
            "date": stock_data["date"],
            "current_price": stock_data["current_price"],
            "currency": stock_data.get("currency", "$"),
            "decision": verdict["decision"],
            "confidence": verdict["confidence"],
            "reasoning": verdict["reasoning"],
            "winner": verdict["winner"],
            "agent_views": analyst_views,
            "debate_rounds": debate_rounds,
            "mode": "debate",
            "data": stock_data,
        }
