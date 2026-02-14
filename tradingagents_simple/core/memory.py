"""
Trading Memory - Persistent storage for decisions and agent performance tracking
Phase 4: Learn from past decisions to improve future ones
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional


class TradingMemory:
    """
    Stores trading decisions and tracks outcomes to build agent accuracy profiles.

    Storage: JSON file with two sections:
    - decisions: Every decision made (ticker, date, agents, verdict)
    - agent_stats: Rolling accuracy per agent (correct/total predictions)
    """

    def __init__(self, memory_dir: str = None):
        if memory_dir is None:
            memory_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(memory_dir, exist_ok=True)
        self.memory_file = os.path.join(memory_dir, "trading_memory.json")
        self._data = self._load()

    def _load(self) -> Dict:
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r") as f:
                return json.load(f)
        return {"decisions": [], "agent_stats": {}}

    def _save(self):
        with open(self.memory_file, "w") as f:
            json.dump(self._data, f, indent=2, default=str)

    def record_decision(self, result: Dict[str, Any]):
        """Record a trading decision for future evaluation"""
        entry = {
            "id": len(self._data["decisions"]) + 1,
            "ticker": result["ticker"],
            "date": result["date"],
            "price_at_decision": result["current_price"],
            "decision": result["decision"],
            "confidence": result["confidence"],
            "mode": result.get("mode", "unknown"),
            "agent_views": [
                {"agent": v["agent"], "view": v["view"], "confidence": v["confidence"]}
                for v in result.get("agent_views", [])
            ],
            "winner": result.get("winner"),
            "recorded_at": datetime.now().isoformat(),
            "outcome": None,  # Filled later by evaluate()
        }
        self._data["decisions"].append(entry)
        self._save()
        return entry["id"]

    def evaluate_decisions(self, data_fetcher) -> List[Dict]:
        """
        Check past decisions against actual price movement.
        Returns list of newly evaluated decisions.
        """
        evaluated = []
        for entry in self._data["decisions"]:
            if entry["outcome"] is not None:
                continue
            try:
                current_data = data_fetcher.fetch_stock_data(entry["ticker"])
                current_price = current_data["current_price"]
                entry_price = entry["price_at_decision"]
                pct_change = ((current_price - entry_price) / entry_price) * 100

                # Was the decision correct?
                # TODO(human)
                correct = self._evaluate_correctness(
                    entry["decision"], pct_change
                )

                entry["outcome"] = {
                    "price_now": current_price,
                    "pct_change": round(pct_change, 2),
                    "correct": correct,
                    "evaluated_at": datetime.now().isoformat(),
                }

                # Update agent stats
                self._update_agent_stats(entry, correct)
                evaluated.append(entry)
            except Exception:
                continue

        if evaluated:
            self._save()
        return evaluated

    def _evaluate_correctness(self, decision: str, pct_change: float) -> bool:
        """Determine if a decision was correct given price movement"""
        # Placeholder — user will implement the scoring logic
        if decision == "BUY":
            return pct_change > 1.0
        elif decision == "SELL":
            return pct_change < -1.0
        else:  # HOLD
            return abs(pct_change) < 3.0

    def _update_agent_stats(self, entry: Dict, overall_correct: bool):
        """Update per-agent accuracy stats based on outcome"""
        stats = self._data["agent_stats"]
        for av in entry.get("agent_views", []):
            agent = av["agent"]
            if agent not in stats:
                stats[agent] = {"correct": 0, "total": 0, "accuracy": 0.0}

            # Agent was "correct" if their view aligned with what happened
            pct = entry["outcome"]["pct_change"]
            view = av["view"]
            if (view == "BULLISH" and pct > 1.0) or \
               (view == "BEARISH" and pct < -1.0) or \
               (view == "NEUTRAL" and abs(pct) < 3.0):
                stats[agent]["correct"] += 1

            stats[agent]["total"] += 1
            stats[agent]["accuracy"] = round(
                stats[agent]["correct"] / stats[agent]["total"], 3
            )

    def get_agent_stats(self) -> Dict[str, Dict]:
        """Get accuracy stats for all agents"""
        return self._data["agent_stats"]

    def get_agent_weight(self, agent_name: str) -> float:
        """Get reliability weight for an agent (0.5 to 1.5 range)"""
        stats = self._data["agent_stats"].get(agent_name)
        if not stats or stats["total"] < 3:
            return 1.0  # Neutral weight until enough data
        # Scale accuracy (0-1) to weight (0.5-1.5)
        return 0.5 + stats["accuracy"]

    def get_recent_decisions(self, ticker: str = None, limit: int = 10) -> List[Dict]:
        """Get recent decisions, optionally filtered by ticker"""
        decisions = self._data["decisions"]
        if ticker:
            decisions = [d for d in decisions if d["ticker"] == ticker]
        return decisions[-limit:]

    def get_summary(self) -> Dict:
        """Overall memory summary"""
        decisions = self._data["decisions"]
        evaluated = [d for d in decisions if d["outcome"] is not None]
        correct = [d for d in evaluated if d["outcome"]["correct"]]
        return {
            "total_decisions": len(decisions),
            "evaluated": len(evaluated),
            "correct": len(correct),
            "accuracy": round(len(correct) / len(evaluated), 3) if evaluated else 0,
            "agents_tracked": len(self._data["agent_stats"]),
        }
