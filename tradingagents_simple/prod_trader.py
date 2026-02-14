"""
Production Trader - Phase 5: Full Pipeline
Analysts → Debate → Risk Manager → Broker → Alerts → Memory

Usage:
    python prod_trader.py NVDA                    # Dry run (safe)
    python prod_trader.py NVDA AAPL --broker paper # Alpaca paper trading
    python prod_trader.py --portfolio              # Show broker portfolio
    python prod_trader.py --evaluate               # Evaluate past decisions
    python prod_trader.py --stats                  # Agent performance stats
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
from core.risk_manager import RiskManager
from core.broker import BrokerInterface
from core.alerts import AlertManager
from config import (
    DEFAULT_CONFIG, FALLBACK_CONFIG, DATA_CONFIG, RISK_CONFIG,
    BROKER_CONFIG, ALERT_CONFIG,
)

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Production Trading System")
    parser.add_argument("tickers", nargs="*", help="Stock ticker(s)")
    parser.add_argument("--date", help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--rounds", type=int, default=2, help="Debate rounds")
    parser.add_argument("--broker", choices=["dry", "paper", "live"], default="dry",
                        help="Broker mode: dry (default), paper (Alpaca), live (Alpaca)")
    parser.add_argument("--portfolio", action="store_true", help="Show broker portfolio")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate past decisions")
    parser.add_argument("--stats", action="store_true", help="Agent accuracy stats")
    parser.add_argument("--history", metavar="TICKER", help="Decision history")
    args = parser.parse_args()

    memory = TradingMemory()
    data_fetcher = DataFetcher(DATA_CONFIG)

    # Utility commands
    if args.stats:
        display_stats(memory)
        return
    if args.history:
        display_history(memory, args.history)
        return
    if args.evaluate:
        evaluate_past(memory, data_fetcher)
        return

    # Map broker mode
    broker_mode = {"dry": "dry_run", "paper": "alpaca_paper", "live": "alpaca_live"}[args.broker]

    if args.portfolio:
        broker = BrokerInterface(mode=broker_mode, config=BROKER_CONFIG)
        display_portfolio(broker)
        return

    if not args.tickers:
        parser.print_help()
        return

    # Safety check for live trading
    if args.broker == "live":
        console.print("\n[bold red]⚠️  LIVE TRADING MODE[/bold red]")
        console.print("[red]This will execute REAL trades with REAL money![/red]")
        confirm = input("Type 'YES I UNDERSTAND' to continue: ")
        if confirm != "YES I UNDERSTAND":
            console.print("[dim]Aborted.[/dim]")
            return

    # Initialize components
    console.print(f"\n[bold green]{'='*60}[/bold green]")
    console.print(f"[bold green]  🚀 Production Trader - Phase 5[/bold green]")
    console.print(f"[bold green]{'='*60}[/bold green]")

    broker = BrokerInterface(mode=broker_mode, config=BROKER_CONFIG)
    risk_mgr = RiskManager(RISK_CONFIG)
    alerts = AlertManager(ALERT_CONFIG)

    mode_icon = {"dry_run": "🧪", "alpaca_paper": "📄", "alpaca_live": "💰"}
    console.print(f"  Mode:    {mode_icon.get(broker_mode, '?')} {broker_mode}")
    console.print(f"  Model:   {DEFAULT_CONFIG.get('model', 'N/A')}")
    console.print(f"  Risk:    max ${RISK_CONFIG['max_position_size']}/trade, "
                   f"{RISK_CONFIG['max_positions']} positions")

    summary = memory.get_summary()
    if summary["total_decisions"] > 0:
        console.print(f"  Memory:  {summary['total_decisions']} decisions, "
                       f"{summary['accuracy']:.0%} accuracy")

    console.print(f"  Stocks:  {', '.join(args.tickers)}")
    console.print(f"[bold green]{'='*60}[/bold green]")

    try:
        llm = LLMInterface(DEFAULT_CONFIG, fallback_config=FALLBACK_CONFIG)
        orchestrator = DebateOrchestrator(llm, data_fetcher, num_rounds=args.rounds)

        results = []
        for ticker in args.tickers:
            ticker = ticker.upper()

            # Show past context
            past = memory.get_recent_decisions(ticker, limit=2)
            if past:
                parts = []
                for p in past:
                    outcome = ""
                    if p["outcome"]:
                        oc = p["outcome"]
                        outcome = f"{'✓' if oc['correct'] else '✗'} {oc['pct_change']:+.1f}%"
                    parts.append(f"{p['decision']}({p['confidence']:.0%}) {outcome}")
                console.print(f"\n  [dim]📜 Recent: {'  '.join(parts)}[/dim]")

            # 1. Analyze & Debate
            decision = orchestrator.analyze_and_decide(ticker, args.date)

            # 2. Risk Check
            risk_result = risk_mgr.evaluate(decision)
            risk_icon = "✅" if risk_result["approved"] else "🚫"
            console.print(f"\n  {risk_icon} Risk: {risk_result['reason']}")

            # 3. Execute
            execution = broker.execute(risk_result)
            if execution.get("executed"):
                console.print(f"  📤 Executed: {execution['order_id']} "
                               f"({execution.get('mode', 'unknown')})")

            # 4. Alert
            alerts.send(decision, risk_result, execution)

            # 5. Memory
            decision_id = memory.record_decision(decision)
            console.print(f"  [dim]💾 Memory #{decision_id}[/dim]")

            # Display
            results.append({**decision, "risk": risk_result, "execution": execution})
            display_verdict(decision, risk_result, execution)

        if len(results) > 1:
            display_summary(results)

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def display_verdict(decision: dict, risk: dict, execution: dict):
    """Display final verdict with risk and execution status"""
    color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[decision["decision"]]
    winner_icon = {"bull": "🐂", "bear": "🐻", "tie": "🤝"}.get(decision.get("winner", "tie"), "🤝")

    status_line = ""
    if not risk["approved"]:
        status_line = f"\n[red]🚫 {risk['reason']}[/red]"
    elif execution.get("executed"):
        status_line = (f"\n[green]📤 Order {execution['order_id']} | "
                       f"{risk['shares']} shares @ ${decision['current_price']:.2f}[/green]")
        if risk.get("stop_loss"):
            status_line += f"\n   SL: ${risk['stop_loss']:.2f} | TP: ${risk['take_profit']:.2f}"

    console.print(Panel(
        f"[bold {color}]{decision['decision']}[/bold {color}] "
        f"({decision['confidence']:.0%}) | Winner: {winner_icon}\n\n"
        f"{decision['reasoning']}"
        f"{status_line}",
        title=f"🚀 {decision['ticker']} - ${decision['current_price']:.2f}",
        border_style=color,
    ))


def display_summary(results: list):
    """Portfolio action summary"""
    console.print(f"\n[bold green]{'='*60}[/bold green]")
    console.print(f"[bold green]  EXECUTION SUMMARY[/bold green]")
    console.print(f"[bold green]{'='*60}[/bold green]\n")

    table = Table(box=box.ROUNDED)
    table.add_column("Ticker", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Decision", justify="center")
    table.add_column("Risk", justify="center")
    table.add_column("Shares", justify="center")
    table.add_column("Size", justify="right")
    table.add_column("Status", justify="center")

    total_deployed = 0
    for r in results:
        dc = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[r["decision"]]
        risk = r["risk"]
        exe = r["execution"]

        approved = "✅" if risk["approved"] else "🚫"
        status = "—"
        if exe.get("executed"):
            status = f"[green]{exe['order_id']}[/green]"
            total_deployed += risk["position_size"]
        elif not risk["approved"]:
            status = "[red]Blocked[/red]"

        table.add_row(
            r["ticker"],
            f"${r['current_price']:.2f}",
            f"[{dc}]{r['decision']}[/{dc}]",
            approved,
            str(risk["shares"]),
            f"${risk['position_size']:.2f}" if risk["position_size"] else "—",
            status,
        )

    console.print(table)
    console.print(f"[dim]Total deployed: ${total_deployed:.2f}[/dim]\n")


def display_stats(memory):
    """Reuse from memory_trader"""
    console.print(f"\n[bold green]🧠 Agent Performance[/bold green]\n")
    stats = memory.get_agent_stats()
    if not stats:
        console.print("[dim]No data yet.[/dim]")
        return
    table = Table(box=box.ROUNDED)
    table.add_column("Agent", style="bold")
    table.add_column("Accuracy", justify="center")
    table.add_column("Correct/Total", justify="center")
    table.add_column("Weight", justify="center")
    for agent, s in sorted(stats.items(), key=lambda x: x[1]["accuracy"], reverse=True):
        ac = "green" if s["accuracy"] >= 0.6 else "yellow" if s["accuracy"] >= 0.4 else "red"
        table.add_row(agent, f"[{ac}]{s['accuracy']:.0%}[/{ac}]",
                       f"{s['correct']}/{s['total']}", f"{memory.get_agent_weight(agent):.2f}x")
    console.print(table)


def display_history(memory, ticker):
    decisions = memory.get_recent_decisions(ticker.upper(), limit=20)
    if not decisions:
        console.print(f"[dim]No history for {ticker.upper()}[/dim]")
        return
    console.print(f"\n[bold]📜 {ticker.upper()} History[/bold]\n")
    for d in decisions:
        outcome = "[dim]pending[/dim]"
        if d["outcome"]:
            oc = d["outcome"]
            ok = "✓" if oc["correct"] else "✗"
            c = "green" if oc["correct"] else "red"
            outcome = f"[{c}]{ok} {oc['pct_change']:+.1f}%[/{c}]"
        dc = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[d["decision"]]
        console.print(f"  #{d['id']} {d['date']} [{dc}]{d['decision']}[/{dc}] "
                       f"({d['confidence']:.0%}) @ ${d['price_at_decision']:.2f} {outcome}")


def evaluate_past(memory, data_fetcher):
    console.print(f"\n[bold]🔍 Evaluating...[/bold]\n")
    evaluated = memory.evaluate_decisions(data_fetcher)
    if not evaluated:
        console.print("[dim]Nothing to evaluate.[/dim]")
        return
    for e in evaluated:
        oc = e["outcome"]
        ok = "✓" if oc["correct"] else "✗"
        c = "green" if oc["correct"] else "red"
        console.print(f"  [{c}]{ok}[/{c}] {e['ticker']} {e['decision']} "
                       f"${e['price_at_decision']:.2f} → ${oc['price_now']:.2f} ({oc['pct_change']:+.1f}%)")
    console.print(f"\n[dim]{len(evaluated)} evaluated. Use --stats for accuracy.[/dim]")


def display_portfolio(broker):
    console.print(f"\n[bold]📊 Portfolio[/bold]\n")
    portfolio = broker.get_portfolio()
    if not portfolio:
        console.print("[dim]No portfolio data.[/dim]")
        return
    for k, v in portfolio.items():
        console.print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
