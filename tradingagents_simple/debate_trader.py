"""
Debate Trader - Phase 3: Bull vs Bear Debate System
Analysts inform a structured debate, judge renders final verdict

Usage:
    python debate_trader.py NVDA
    python debate_trader.py NVDA AAPL --rounds 3
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
from config import DEFAULT_CONFIG, DATA_CONFIG

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Bull vs Bear Debate Trader")
    parser.add_argument("tickers", nargs="+", help="Stock ticker(s)")
    parser.add_argument("--date", help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--rounds", type=int, default=2, help="Debate rounds (1-5)")
    args = parser.parse_args()

    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold cyan]  ⚔️  Bull vs Bear Debate - Phase 3[/bold cyan]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"  Analysts: 📊 Technical | 💼 Fundamental | 🎭 Sentiment")
    console.print(f"  Debaters: 🐂 Bull vs 🐻 Bear ({args.rounds} rounds)")
    console.print(f"  Judge:    ⚖️  Portfolio Manager")
    console.print(f"  Model:    {DEFAULT_CONFIG.get('model', 'N/A')}")
    console.print(f"  Stocks:   {', '.join(args.tickers)}")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]")

    try:
        llm = LLMInterface(DEFAULT_CONFIG)
        data_fetcher = DataFetcher(DATA_CONFIG)
        orchestrator = DebateOrchestrator(llm, data_fetcher, num_rounds=args.rounds)

        results = []
        for ticker in args.tickers:
            result = orchestrator.analyze_and_decide(ticker.upper(), args.date)
            results.append(result)
            display_debate_result(result)

        if len(results) > 1:
            display_portfolio_summary(results)

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def display_debate_result(result: dict):
    """Display full debate result with rounds"""
    color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[result["decision"]]

    # Analyst views
    console.print(f"\n[bold]Analyst Views for {result['ticker']}:[/bold]")
    agent_table = Table(box=box.SIMPLE, show_header=True)
    agent_table.add_column("Agent", style="bold", width=20)
    agent_table.add_column("View", justify="center", width=10)
    agent_table.add_column("Conf.", justify="center", width=8)
    agent_table.add_column("Analysis", width=50)

    for v in result["agent_views"]:
        vc = {"BULLISH": "green", "BEARISH": "red", "NEUTRAL": "yellow"}[v["view"]]
        agent_table.add_row(
            v["agent"], f"[{vc}]{v['view']}[/{vc}]",
            f"{v['confidence']:.0%}",
            v["analysis"][:50] + "..." if len(v["analysis"]) > 50 else v["analysis"],
        )
    console.print(agent_table)

    # Debate rounds
    console.print(f"\n[bold]Debate Rounds:[/bold]")
    for i, rnd in enumerate(result["debate_rounds"], 1):
        bull = rnd["bull"]
        bear = rnd["bear"]
        console.print(f"\n  [bold]Round {i}[/bold]")
        console.print(f"  [green]🐂 Bull ({bull['conviction']:.0%}):[/green] {bull['argument'][:120]}...")
        console.print(f"  [red]🐻 Bear ({bear['conviction']:.0%}):[/red] {bear['argument'][:120]}...")

    # Final verdict
    winner_icon = {"bull": "🐂", "bear": "🐻", "tie": "🤝"}[result["winner"]]
    console.print(Panel(
        f"[bold {color}]{result['decision']}[/bold {color}] "
        f"(Confidence: {result['confidence']:.0%})\n"
        f"Winner: {winner_icon} {result['winner'].upper()}\n\n"
        f"{result['reasoning']}",
        title=f"⚖️  VERDICT: {result['ticker']} - ${result['current_price']:.2f}",
        border_style=color,
    ))


def display_portfolio_summary(results: list):
    """Portfolio summary for multiple stocks"""
    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold cyan]  PORTFOLIO SUMMARY (Debate System)[/bold cyan]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")

    table = Table(title="Debate Trading Decisions", box=box.ROUNDED)
    table.add_column("Ticker", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Decision", justify="center")
    table.add_column("Conf.", justify="center")
    table.add_column("Winner", justify="center")
    table.add_column("Bull Conv.", justify="center")
    table.add_column("Bear Conv.", justify="center")

    for r in results:
        dc = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[r["decision"]]
        wi = {"bull": "[green]🐂[/green]", "bear": "[red]🐻[/red]", "tie": "🤝"}[r["winner"]]
        # Average conviction across rounds
        last_round = r["debate_rounds"][-1]
        table.add_row(
            r["ticker"],
            f"${r['current_price']:.2f}",
            f"[{dc}]{r['decision']}[/{dc}]",
            f"{r['confidence']:.0%}",
            wi,
            f"{last_round['bull']['conviction']:.0%}",
            f"{last_round['bear']['conviction']:.0%}",
        )

    console.print(table)
    console.print(f"[dim]🐂 = Bull won  🐻 = Bear won  🤝 = Tie[/dim]\n")


if __name__ == "__main__":
    main()
