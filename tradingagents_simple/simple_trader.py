"""
Simple Trader - Phase 1 MVP
A minimal but extensible single-agent trading system

Usage:
    python simple_trader.py NVDA                    # AI mode (DeepSeek)
    python simple_trader.py NVDA --mode rules       # Rule-based (free, no API)
    python simple_trader.py AAPL --date 2024-01-15  # Specific date
    python simple_trader.py NVDA AAPL TSLA          # Multiple stocks
"""
import sys
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from core.agent import TradingAgent
from core.llm import LLMInterface
from core.data import DataFetcher
from config import DEFAULT_CONFIG, DATA_CONFIG

console = Console()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Simple AI Trading Agent")
    parser.add_argument("tickers", nargs="+", help="Stock ticker(s) (e.g., NVDA AAPL TSLA)")
    parser.add_argument("--date", help="Analysis date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--mode", choices=["llm", "rules"], default="llm",
                        help="Analysis mode: 'llm' (AI-powered) or 'rules' (free, no API)")
    args = parser.parse_args()

    # Header
    mode_label = "🤖 AI (DeepSeek)" if args.mode == "llm" else "📐 Rule-Based (Free)"
    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold cyan]  Simple Trading Agent - Phase 1[/bold cyan]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"  Mode: {mode_label}")
    if args.mode == "llm":
        console.print(f"  Model: {DEFAULT_CONFIG.get('model', 'N/A')}")
    console.print(f"  Stocks: {', '.join(args.tickers)}")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")

    try:
        # Initialize components
        llm = LLMInterface(DEFAULT_CONFIG)
        data_fetcher = DataFetcher(DATA_CONFIG)
        agent = TradingAgent(llm, data_fetcher, mode=args.mode)

        # Analyze each ticker
        results = []
        for ticker in args.tickers:
            result = agent.analyze_and_decide(ticker.upper(), args.date)
            results.append(result)
            display_single_result(result)

        # Summary table for multiple stocks
        if len(results) > 1:
            display_summary(results)

    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def display_single_result(result: dict):
    """Display one stock's trading decision"""
    color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[result["decision"]]
    mode_icon = "🤖" if result.get("mode") == "llm" else "📐"

    console.print(Panel(
        f"[bold {color}]{result['decision']}[/bold {color}] "
        f"(Confidence: {result['confidence']:.0%})\n\n"
        f"{result['reasoning']}",
        title=f"{mode_icon} {result['ticker']} - ${result['current_price']:.2f}",
        border_style=color,
    ))

    # Indicators table
    ind = result["data"]["indicators"]
    table = Table(show_header=True, box=box.SIMPLE)
    table.add_column("Indicator", style="cyan", width=14)
    table.add_column("Value", style="white", width=12)
    table.add_column("Signal", style="dim", width=20)

    # Price change
    pc = ind["price_change_pct"]
    table.add_row("Price Change", f"{pc:.2f}%",
                   "📈 Bullish" if pc > 3 else "📉 Bearish" if pc < -3 else "➡️ Neutral")

    # RSI
    rsi = ind["rsi"]
    if rsi:
        rsi_signal = "🔥 Overbought" if rsi > 70 else "💎 Oversold" if rsi < 30 else "✅ Normal"
        table.add_row("RSI", f"{rsi:.1f}", rsi_signal)

    # SMA 20
    sma = ind["sma_20"]
    if sma:
        above = result["current_price"] > sma
        table.add_row("SMA 20", f"${sma:.2f}", "✅ Above" if above else "⚠️ Below")

    # Volatility
    vol = ind["volatility"]
    if vol:
        table.add_row("Volatility", f"{vol:.2f}%",
                       "⚠️ High" if vol > 3 else "✅ Low" if vol < 1.5 else "➡️ Normal")

    console.print(table)
    console.print(f"[dim]{result['data']['info']['name']} | {result['data']['info']['sector']}[/dim]\n")


def display_summary(results: list):
    """Display summary table for multiple stocks"""
    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold cyan]  PORTFOLIO SUMMARY[/bold cyan]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")

    table = Table(title="Trading Decisions", box=box.ROUNDED)
    table.add_column("Ticker", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Decision", justify="center")
    table.add_column("Confidence", justify="center")
    table.add_column("Reasoning")

    for r in results:
        color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[r["decision"]]
        table.add_row(
            r["ticker"],
            f"${r['current_price']:.2f}",
            f"[{color}]{r['decision']}[/{color}]",
            f"{r['confidence']:.0%}",
            r["reasoning"][:50] + "..." if len(r["reasoning"]) > 50 else r["reasoning"],
        )

    console.print(table)

    # Stats
    buys = sum(1 for r in results if r["decision"] == "BUY")
    sells = sum(1 for r in results if r["decision"] == "SELL")
    holds = sum(1 for r in results if r["decision"] == "HOLD")
    console.print(f"\n  [green]BUY: {buys}[/green] | [red]SELL: {sells}[/red] | [yellow]HOLD: {holds}[/yellow]\n")


if __name__ == "__main__":
    main()
