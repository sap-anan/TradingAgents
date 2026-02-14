"""
Team Trader - Phase 2: Multi-Agent System
3 specialist agents collaborate to make trading decisions

Usage:
    python team_trader.py NVDA
    python team_trader.py NVDA AAPL TSLA
"""
import sys
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from agents.team import AgentTeam
from core.llm import LLMInterface
from core.data import DataFetcher
from config import DEFAULT_CONFIG, DATA_CONFIG

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Trading Team")
    parser.add_argument("tickers", nargs="+", help="Stock ticker(s)")
    parser.add_argument("--date", help="Analysis date (YYYY-MM-DD)")
    args = parser.parse_args()

    console.print(f"\n[bold magenta]{'='*60}[/bold magenta]")
    console.print(f"[bold magenta]  🏢 Multi-Agent Trading Team - Phase 2[/bold magenta]")
    console.print(f"[bold magenta]{'='*60}[/bold magenta]")
    console.print(f"  Agents: 📊 Technical | 💼 Fundamental | 🎭 Sentiment")
    console.print(f"  Model: {DEFAULT_CONFIG.get('model', 'N/A')}")
    console.print(f"  Stocks: {', '.join(args.tickers)}")
    console.print(f"[bold magenta]{'='*60}[/bold magenta]")

    try:
        llm = LLMInterface(DEFAULT_CONFIG)
        data_fetcher = DataFetcher(DATA_CONFIG)
        team = AgentTeam(llm, data_fetcher)

        results = []
        for ticker in args.tickers:
            result = team.analyze_and_decide(ticker.upper(), args.date)
            results.append(result)
            display_team_result(result)

        if len(results) > 1:
            display_portfolio_summary(results)

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def display_team_result(result: dict):
    """Display multi-agent analysis result"""
    color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[result["decision"]]

    # Agent views table
    console.print(f"\n[bold]Agent Views for {result['ticker']}:[/bold]")
    agent_table = Table(box=box.SIMPLE, show_header=True)
    agent_table.add_column("Agent", style="bold", width=20)
    agent_table.add_column("View", justify="center", width=10)
    agent_table.add_column("Conf.", justify="center", width=8)
    agent_table.add_column("Analysis", width=50)

    for v in result["agent_views"]:
        v_color = {"BULLISH": "green", "BEARISH": "red", "NEUTRAL": "yellow"}[v["view"]]
        agent_table.add_row(
            v["agent"],
            f"[{v_color}]{v['view']}[/{v_color}]",
            f"{v['confidence']:.0%}",
            v["analysis"][:50] + "..." if len(v["analysis"]) > 50 else v["analysis"],
        )

    console.print(agent_table)

    # Final decision
    console.print(Panel(
        f"[bold {color}]{result['decision']}[/bold {color}] "
        f"(Confidence: {result['confidence']:.0%})\n\n"
        f"{result['reasoning']}",
        title=f"🏢 FINAL: {result['ticker']} - ${result['current_price']:.2f}",
        border_style=color,
    ))


def display_portfolio_summary(results: list):
    """Display summary for multiple stocks"""
    console.print(f"\n[bold magenta]{'='*60}[/bold magenta]")
    console.print(f"[bold magenta]  PORTFOLIO SUMMARY (Multi-Agent)[/bold magenta]")
    console.print(f"[bold magenta]{'='*60}[/bold magenta]\n")

    table = Table(title="Team Trading Decisions", box=box.ROUNDED)
    table.add_column("Ticker", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Decision", justify="center")
    table.add_column("Conf.", justify="center")
    table.add_column("Tech", justify="center")
    table.add_column("Fund", justify="center")
    table.add_column("Sent", justify="center")

    for r in results:
        dc = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[r["decision"]]
        views = {v["agent"]: v for v in r["agent_views"]}

        def view_cell(agent_name):
            v = views.get(agent_name, {})
            vc = {"BULLISH": "green", "BEARISH": "red", "NEUTRAL": "yellow"}.get(v.get("view", ""), "dim")
            symbol = {"BULLISH": "▲", "BEARISH": "▼", "NEUTRAL": "─"}.get(v.get("view", ""), "?")
            return f"[{vc}]{symbol}[/{vc}]"

        table.add_row(
            r["ticker"],
            f"${r['current_price']:.2f}",
            f"[{dc}]{r['decision']}[/{dc}]",
            f"{r['confidence']:.0%}",
            view_cell("Technical Analyst"),
            view_cell("Fundamental Analyst"),
            view_cell("Sentiment Analyst"),
        )

    console.print(table)
    console.print(f"[dim]▲ = Bullish  ▼ = Bearish  ─ = Neutral[/dim]\n")


if __name__ == "__main__":
    main()
