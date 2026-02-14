"""
Bitkub Trader - Crypto Trading via Bitkub Exchange
Full pipeline: Data → Analysts → Debate → Risk → Execute → Alert → Memory

Usage:
    python bitkub_trader.py BTC                  # Dry run (safe, default)
    python bitkub_trader.py BTC ETH --rounds 3   # Multiple coins, 3 debate rounds
    python bitkub_trader.py --list-coins          # Show all Bitkub symbols
    python bitkub_trader.py --balances            # Show real wallet (needs API key)
    python bitkub_trader.py BTC --live            # REAL trades (⚠️ real THB!)
    python bitkub_trader.py --scan                # Scan top 10 coins by volume
    python bitkub_trader.py --scan 20             # Scan top 20
    python bitkub_trader.py --watchlist           # Analyze saved watchlist
"""
import sys
import os
import json
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from agents.debate.orchestrator import DebateOrchestrator
from core.llm import LLMInterface
from core.bitkub_data import BitkubDataFetcher
from core.bitkub_client import BitkubClient
from core.memory import TradingMemory
from core.risk_manager import RiskManager
from core.broker import BrokerInterface
from core.alerts import AlertManager
from config import (
    DEFAULT_CONFIG, FALLBACK_CONFIG, BITKUB_CONFIG, BITKUB_DATA_CONFIG,
    CRYPTO_RISK_CONFIG, ALERT_CONFIG,
)

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Bitkub Crypto Trader — Leviathan First Pond")
    parser.add_argument("coins", nargs="*", help="Coin(s) to analyze: BTC, ETH, ADA...")
    parser.add_argument("--date", help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--rounds", type=int, default=2, help="Debate rounds (default: 2)")
    parser.add_argument("--live", action="store_true", help="LIVE trading (real THB!)")
    parser.add_argument("--list-coins", action="store_true", help="List all Bitkub symbols")
    parser.add_argument("--balances", action="store_true", help="Show Bitkub wallet balances")
    parser.add_argument("--scan", nargs="?", const=10, type=int, metavar="N",
                        help="Scan top N coins by volume (default: 10)")
    parser.add_argument("--watchlist", action="store_true", help="Analyze saved watchlist coins")
    parser.add_argument("--watchlist-add", nargs="+", metavar="COIN", help="Add coins to watchlist")
    parser.add_argument("--watchlist-remove", nargs="+", metavar="COIN", help="Remove coins from watchlist")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate past decisions")
    parser.add_argument("--stats", action="store_true", help="Agent accuracy stats")
    parser.add_argument("--history", metavar="COIN", help="Decision history for a coin")
    args = parser.parse_args()

    # ─── Utility commands (no LLM needed) ───────────────────────

    if args.list_coins:
        list_coins()
        return

    if args.balances:
        show_balances()
        return

    if args.scan is not None:
        scan_top_coins(args.scan)
        return

    if args.watchlist_add:
        watchlist_modify(add=args.watchlist_add)
        return

    if args.watchlist_remove:
        watchlist_modify(remove=args.watchlist_remove)
        return

    if args.watchlist:
        coins = load_watchlist()
        if not coins:
            console.print("[dim]Watchlist empty. Add coins: --watchlist-add BTC ETH ADA[/dim]")
            return
        args.coins = coins
        console.print(f"[cyan]Watchlist: {', '.join(coins)}[/cyan]")

    memory = TradingMemory()
    data_fetcher = BitkubDataFetcher(BITKUB_DATA_CONFIG)

    if args.stats:
        display_stats(memory)
        return
    if args.history:
        display_history(memory, args.history)
        return
    if args.evaluate:
        evaluate_past(memory, data_fetcher)
        return

    if not args.coins:
        parser.print_help()
        return

    # ─── Broker mode ────────────────────────────────────────────

    broker_mode = "bitkub_live" if args.live else "bitkub_dry"
    broker_config = BITKUB_CONFIG if args.live else {}

    # Safety check for live trading
    if args.live:
        console.print("\n[bold red]⚠️  BITKUB LIVE TRADING MODE[/bold red]")
        console.print("[red]This will execute REAL trades with REAL THB![/red]")
        confirm = input("Type 'YES I UNDERSTAND' to continue: ")
        if confirm != "YES I UNDERSTAND":
            console.print("[dim]Aborted.[/dim]")
            return

    # ─── Initialize pipeline ────────────────────────────────────

    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold cyan]  🦈 Bitkub Trader — Leviathan First Pond[/bold cyan]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]")

    broker = BrokerInterface(mode=broker_mode, config=broker_config)
    risk_mgr = RiskManager(CRYPTO_RISK_CONFIG)
    alerts = AlertManager(ALERT_CONFIG)

    mode_icon = "🧪" if broker_mode == "bitkub_dry" else "💰"
    console.print(f"  Mode:      {mode_icon} {broker_mode}")
    console.print(f"  Model:     {DEFAULT_CONFIG.get('model', 'N/A')}")
    console.print(f"  Risk:      max ฿{CRYPTO_RISK_CONFIG['max_position_size']:,}/trade, "
                   f"{CRYPTO_RISK_CONFIG['max_positions']} positions")
    console.print(f"  Currency:  THB")

    summary = memory.get_summary()
    if summary["total_decisions"] > 0:
        console.print(f"  Memory:    {summary['total_decisions']} decisions, "
                       f"{summary['accuracy']:.0%} accuracy")

    console.print(f"  Coins:     {', '.join(c.upper() for c in args.coins)}")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]")

    try:
        llm = LLMInterface(DEFAULT_CONFIG, fallback_config=FALLBACK_CONFIG)
        orchestrator = DebateOrchestrator(llm, data_fetcher, num_rounds=args.rounds)

        results = []
        for coin in args.coins:
            coin = coin.upper()

            # Show past context
            past = memory.get_recent_decisions(coin, limit=2)
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
            decision = orchestrator.analyze_and_decide(coin, args.date)

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

            results.append({**decision, "risk": risk_result, "execution": execution})
            display_verdict(decision, risk_result, execution)

        if len(results) > 1:
            display_summary(results)

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ─── Watchlist & Scan ───────────────────────────────────────────

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "data", "watchlist.json")


def load_watchlist() -> list:
    """Load saved watchlist"""
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE) as f:
            return json.load(f)
    return []


def save_watchlist(coins: list):
    """Save watchlist"""
    os.makedirs(os.path.dirname(WATCHLIST_FILE), exist_ok=True)
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(sorted(set(coins)), f)


def watchlist_modify(add: list = None, remove: list = None):
    """Add or remove coins from watchlist"""
    coins = load_watchlist()
    if add:
        new_coins = [c.upper() for c in add]
        coins = sorted(set(coins + new_coins))
        save_watchlist(coins)
        console.print(f"[green]Added: {', '.join(new_coins)}[/green]")
    if remove:
        rm_coins = [c.upper() for c in remove]
        coins = [c for c in coins if c not in rm_coins]
        save_watchlist(coins)
        console.print(f"[red]Removed: {', '.join(rm_coins)}[/red]")
    console.print(f"[cyan]Watchlist: {', '.join(coins) if coins else '(empty)'}[/cyan]")


def scan_top_coins(n: int = 10):
    """Scan top N coins by 24h volume — quick market overview"""
    console.print(f"\n[bold cyan]📡 Scanning Top {n} Coins by Volume[/bold cyan]\n")
    try:
        client = BitkubClient()
        ticker_data = client.ticker()
        if not isinstance(ticker_data, dict):
            console.print("[red]Failed to fetch data[/red]")
            return

        # Sort by quote volume (THB traded)
        ranked = sorted(
            ticker_data.items(),
            key=lambda x: float(x[1].get("quote_volume", 0)),
            reverse=True,
        )[:n]

        table = Table(title=f"Top {n} by 24h Volume", box=box.ROUNDED)
        table.add_column("#", style="dim", width=3)
        table.add_column("Coin", style="bold cyan")
        table.add_column("Price (THB)", justify="right")
        table.add_column("24h Change", justify="right")
        table.add_column("24h Volume (THB)", justify="right", style="yellow")
        table.add_column("Signal", justify="center")

        for i, (sym, t) in enumerate(ranked, 1):
            coin = BitkubClient.from_symbol(sym)
            price = float(t.get("last", 0))
            change = float(t.get("percent_change", 0))
            volume = float(t.get("quote_volume", 0))

            change_color = "green" if change >= 0 else "red"

            # Quick signal based on 24h change
            if change > 5:
                signal = "[green]HOT[/green]"
            elif change > 0:
                signal = "[green]UP[/green]"
            elif change > -5:
                signal = "[red]DOWN[/red]"
            else:
                signal = "[red]DUMP[/red]"

            table.add_row(
                str(i), coin,
                f"฿{price:,.2f}",
                f"[{change_color}]{change:+.2f}%[/{change_color}]",
                f"฿{volume:,.0f}",
                signal,
            )

        console.print(table)
        console.print(f"\n[dim]Tip: python bitkub_trader.py {BitkubClient.from_symbol(ranked[0][0])} "
                       f"{BitkubClient.from_symbol(ranked[1][0])} — to analyze top coins[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# ─── Display Functions ──────────────────────────────────────────

def list_coins():
    """List all available coins on Bitkub"""
    console.print(f"\n[bold cyan]🪙 Bitkub Available Coins[/bold cyan]\n")
    try:
        client = BitkubClient()
        ticker_data = client.ticker()
        if not isinstance(ticker_data, dict):
            console.print("[red]Failed to fetch ticker data[/red]")
            return

        table = Table(box=box.ROUNDED)
        table.add_column("Symbol", style="bold")
        table.add_column("Coin", style="cyan")
        table.add_column("Price (THB)", justify="right")
        table.add_column("24h Change", justify="right")
        table.add_column("Volume (THB)", justify="right")

        for sym in sorted(ticker_data.keys()):
            t = ticker_data[sym]
            coin = BitkubClient.from_symbol(sym)
            price = float(t.get("last", 0))
            change = float(t.get("percent_change", 0))
            volume = float(t.get("quote_volume", 0))

            change_color = "green" if change >= 0 else "red"
            table.add_row(
                sym, coin,
                f"฿{price:,.2f}",
                f"[{change_color}]{change:+.2f}%[/{change_color}]",
                f"฿{volume:,.0f}",
            )

        console.print(table)
        console.print(f"\n[dim]{len(ticker_data)} coins available[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def show_balances():
    """Show Bitkub wallet balances"""
    console.print(f"\n[bold cyan]💰 Bitkub Wallet[/bold cyan]\n")
    try:
        client = BitkubClient(
            api_key=BITKUB_CONFIG.get("api_key"),
            api_secret=BITKUB_CONFIG.get("api_secret"),
        )
        balances = client.balances()

        table = Table(box=box.ROUNDED)
        table.add_column("Currency", style="bold")
        table.add_column("Available", justify="right")
        table.add_column("Reserved", justify="right")

        for currency, bal in sorted(balances.items()):
            avail = float(bal.get("available", 0))
            reserved = float(bal.get("reserved", 0))
            if avail > 0 or reserved > 0:
                table.add_row(currency, f"{avail:,.8f}", f"{reserved:,.8f}")

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Set BITKUB_API_KEY and BITKUB_API_SECRET in .env[/dim]")


def display_verdict(decision: dict, risk: dict, execution: dict):
    """Display final verdict"""
    color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[decision["decision"]]
    winner_icon = {"bull": "🐂", "bear": "🐻", "tie": "🤝"}.get(decision.get("winner", "tie"), "🤝")

    status_line = ""
    if not risk["approved"]:
        status_line = f"\n[red]🚫 {risk['reason']}[/red]"
    elif execution.get("executed"):
        status_line = (f"\n[green]📤 Order {execution['order_id']} | "
                       f"฿{risk['position_size']:,.2f} THB[/green]")
        if risk.get("stop_loss"):
            status_line += f"\n   SL: ฿{risk['stop_loss']:,.2f} | TP: ฿{risk['take_profit']:,.2f}"

    console.print(Panel(
        f"[bold {color}]{decision['decision']}[/bold {color}] "
        f"({decision['confidence']:.0%}) | Winner: {winner_icon}\n\n"
        f"{decision['reasoning']}"
        f"{status_line}",
        title=f"🦈 {decision['ticker']} — ฿{decision['current_price']:,.2f} THB",
        border_style=color,
    ))


def display_summary(results: list):
    """Portfolio action summary"""
    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold cyan]  EXECUTION SUMMARY[/bold cyan]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")

    table = Table(box=box.ROUNDED)
    table.add_column("Coin", style="bold")
    table.add_column("Price (THB)", justify="right")
    table.add_column("Decision", justify="center")
    table.add_column("Risk", justify="center")
    table.add_column("Size (THB)", justify="right")
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
            f"฿{r['current_price']:,.2f}",
            f"[{dc}]{r['decision']}[/{dc}]",
            approved,
            f"฿{risk['position_size']:,.2f}" if risk["position_size"] else "—",
            status,
        )

    console.print(table)
    console.print(f"[dim]Total deployed: ฿{total_deployed:,.2f} THB[/dim]\n")


def display_stats(memory):
    console.print(f"\n[bold cyan]🧠 Agent Performance (Crypto)[/bold cyan]\n")
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


def display_history(memory, coin):
    decisions = memory.get_recent_decisions(coin.upper(), limit=20)
    if not decisions:
        console.print(f"[dim]No history for {coin.upper()}[/dim]")
        return
    console.print(f"\n[bold]📜 {coin.upper()} History[/bold]\n")
    for d in decisions:
        outcome = "[dim]pending[/dim]"
        if d["outcome"]:
            oc = d["outcome"]
            ok = "✓" if oc["correct"] else "✗"
            c = "green" if oc["correct"] else "red"
            outcome = f"[{c}]{ok} {oc['pct_change']:+.1f}%[/{c}]"
        dc = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[d["decision"]]
        console.print(f"  #{d['id']} {d['date']} [{dc}]{d['decision']}[/{dc}] "
                       f"({d['confidence']:.0%}) @ ฿{d['price_at_decision']:,.2f} {outcome}")


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
                       f"฿{e['price_at_decision']:,.2f} → ฿{oc['price_now']:,.2f} ({oc['pct_change']:+.1f}%)")
    console.print(f"\n[dim]{len(evaluated)} evaluated. Use --stats for accuracy.[/dim]")


if __name__ == "__main__":
    main()
