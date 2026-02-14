"""
Memory Trader - Phase 4: Learning from past decisions
Debate system + persistent memory + agent accuracy tracking

Usage:
    python memory_trader.py NVDA                 # Analyze with memory
    python memory_trader.py NVDA --evaluate      # Check past decisions
    python memory_trader.py --stats              # Show agent accuracy
    python memory_trader.py --history NVDA       # Past decisions for ticker
"""
import sys
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from agents.debate.orchestrator import DebateOrchestrator
from core.llm import LLMInterface
from core.data import DataFetcher
from core.memory import TradingMemory
from config import DEFAULT_CONFIG, DATA_CONFIG

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Memory-Enhanced Debate Trader")
    parser.add_argument("tickers", nargs="*", help="Stock ticker(s)")
    parser.add_argument("--date", help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--rounds", type=int, default=2, help="Debate rounds (1-5)")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate past decisions")
    parser.add_argument("--stats", action="store_true", help="Show agent accuracy stats")
    parser.add_argument("--history", metavar="TICKER", help="Show decision history")
    args = parser.parse_args()

    memory = TradingMemory()
    data_fetcher = DataFetcher(DATA_CONFIG)

    if args.stats:
        display_stats(memory)
        return

    if args.history:
        display_history(memory, args.history)
        return

    if args.evaluate:
        evaluate_past(memory, data_fetcher)
        return

    if not args.tickers:
        parser.print_help()
        return

    console.print(f"\n[bold blue]{'='*60}[/bold blue]")
    console.print(f"[bold blue]  🧠 Memory-Enhanced Debate Trader - Phase 4[/bold blue]")
    console.print(f"[bold blue]{'='*60}[/bold blue]")

    summary = memory.get_summary()
    if summary["total_decisions"] > 0:
        console.print(f"  Memory: {summary['total_decisions']} decisions, "
                       f"{summary['accuracy']:.0%} accuracy")
    else:
        console.print(f"  Memory: Empty (first run!)")

    agent_stats = memory.get_agent_stats()
    if agent_stats:
        weights = ", ".join(
            f"{a}: {memory.get_agent_weight(a):.2f}x"
            for a in agent_stats
        )
        console.print(f"  Agent Weights: {weights}")

    console.print(f"  Model: {DEFAULT_CONFIG.get('model', 'N/A')}")
    console.print(f"[bold blue]{'='*60}[/bold blue]")

    try:
        llm = LLMInterface(DEFAULT_CONFIG)
        orchestrator = DebateOrchestrator(llm, data_fetcher, num_rounds=args.rounds)

        results = []
        for ticker in args.tickers:
            # Show past context if available
            past = memory.get_recent_decisions(ticker.upper(), limit=3)
            if past:
                console.print(f"\n  [dim]📜 Past decisions for {ticker.upper()}:[/dim]")
                for p in past:
                    outcome = ""
                    if p["outcome"]:
                        oc = p["outcome"]
                        outcome = f" → {'✓' if oc['correct'] else '✗'} ({oc['pct_change']:+.1f}%)"
                    console.print(f"     {p['date']}: {p['decision']} ({p['confidence']:.0%}){outcome}")

            result = orchestrator.analyze_and_decide(ticker.upper(), args.date)

            # Record to memory
            decision_id = memory.record_decision(result)
            console.print(f"\n  [dim]💾 Saved as decision #{decision_id}[/dim]")

            results.append(result)
            display_result(result)

        if len(results) > 1:
            display_portfolio(results)

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def display_result(result: dict):
    """Display debate result"""
    color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[result["decision"]]
    winner_icon = {"bull": "🐂", "bear": "🐻", "tie": "🤝"}[result["winner"]]

    # Debate summary
    for i, rnd in enumerate(result["debate_rounds"], 1):
        bull, bear = rnd["bull"], rnd["bear"]
        console.print(f"\n  [bold]Round {i}:[/bold] "
                       f"[green]🐂 {bull['conviction']:.0%}[/green] vs "
                       f"[red]🐻 {bear['conviction']:.0%}[/red]")

    console.print(Panel(
        f"[bold {color}]{result['decision']}[/bold {color}] "
        f"(Confidence: {result['confidence']:.0%})\n"
        f"Winner: {winner_icon} {result['winner'].upper()}\n\n"
        f"{result['reasoning']}",
        title=f"⚖️  VERDICT: {result['ticker']} - ${result['current_price']:.2f}",
        border_style=color,
    ))


def display_stats(memory: TradingMemory):
    """Show agent accuracy stats"""
    console.print(f"\n[bold blue]🧠 Agent Performance Stats[/bold blue]\n")
    stats = memory.get_agent_stats()

    if not stats:
        console.print("[dim]No data yet. Run some analyses first![/dim]")
        return

    table = Table(box=box.ROUNDED)
    table.add_column("Agent", style="bold")
    table.add_column("Accuracy", justify="center")
    table.add_column("Correct", justify="center")
    table.add_column("Total", justify="center")
    table.add_column("Weight", justify="center")

    for agent, s in sorted(stats.items(), key=lambda x: x[1]["accuracy"], reverse=True):
        acc_color = "green" if s["accuracy"] >= 0.6 else "yellow" if s["accuracy"] >= 0.4 else "red"
        table.add_row(
            agent,
            f"[{acc_color}]{s['accuracy']:.0%}[/{acc_color}]",
            str(s["correct"]),
            str(s["total"]),
            f"{memory.get_agent_weight(agent):.2f}x",
        )

    console.print(table)

    summary = memory.get_summary()
    console.print(f"\n[dim]Overall: {summary['total_decisions']} decisions, "
                   f"{summary['evaluated']} evaluated, {summary['accuracy']:.0%} accuracy[/dim]")


def display_history(memory: TradingMemory, ticker: str):
    """Show decision history for a ticker"""
    console.print(f"\n[bold blue]📜 Decision History: {ticker.upper()}[/bold blue]\n")
    decisions = memory.get_recent_decisions(ticker.upper(), limit=20)

    if not decisions:
        console.print(f"[dim]No history for {ticker.upper()}[/dim]")
        return

    table = Table(box=box.SIMPLE)
    table.add_column("ID", width=4)
    table.add_column("Date", width=12)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Decision", justify="center", width=8)
    table.add_column("Conf.", justify="center", width=6)
    table.add_column("Outcome", width=20)

    for d in decisions:
        dc = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[d["decision"]]
        outcome = "[dim]Pending[/dim]"
        if d["outcome"]:
            oc = d["outcome"]
            ok = "✓" if oc["correct"] else "✗"
            oc_color = "green" if oc["correct"] else "red"
            outcome = f"[{oc_color}]{ok} {oc['pct_change']:+.1f}% → ${oc['price_now']:.2f}[/{oc_color}]"
        table.add_row(
            str(d["id"]), d["date"],
            f"${d['price_at_decision']:.2f}",
            f"[{dc}]{d['decision']}[/{dc}]",
            f"{d['confidence']:.0%}",
            outcome,
        )

    console.print(table)


def evaluate_past(memory: TradingMemory, data_fetcher: DataFetcher):
    """Evaluate unevaluated past decisions"""
    console.print(f"\n[bold blue]🔍 Evaluating Past Decisions...[/bold blue]\n")
    evaluated = memory.evaluate_decisions(data_fetcher)

    if not evaluated:
        console.print("[dim]No pending decisions to evaluate.[/dim]")
        return

    for e in evaluated:
        oc = e["outcome"]
        ok = "✓" if oc["correct"] else "✗"
        color = "green" if oc["correct"] else "red"
        console.print(f"  [{color}]{ok}[/{color}] {e['ticker']} {e['decision']} "
                       f"@ ${e['price_at_decision']:.2f} → ${oc['price_now']:.2f} "
                       f"({oc['pct_change']:+.1f}%)")

    console.print(f"\n[dim]Evaluated {len(evaluated)} decisions. Run --stats to see updated agent accuracy.[/dim]")


if __name__ == "__main__":
    main()
