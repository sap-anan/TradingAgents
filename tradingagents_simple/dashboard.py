"""
Trading Dashboard - Streamlit monitoring UI
Reads from trading_memory.json, trade logs, and watcher snapshots.

Usage:
    streamlit run dashboard.py
"""
import streamlit as st
import json
import os
import glob
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date as date_type

# ─── Config ───
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "trading_memory.json")
LOG_DIR = os.path.join(DATA_DIR, "logs")

# Watcher imports
from watcher import read_jsonl, snapshot_path, event_path, load_watchlist
from core.market_context import MarketContext
from config import WATCHER_CONFIG

st.set_page_config(
    page_title="Leviathan Trading Monitor",
    page_icon="🦈",
    layout="wide",
)

# ─── Session state init ───
if "analysis_running" not in st.session_state:
    st.session_state["analysis_running"] = False


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {"decisions": [], "agent_stats": {}}


def load_trade_logs():
    logs = []
    if os.path.exists(LOG_DIR):
        for f in sorted(glob.glob(os.path.join(LOG_DIR, "trades_*.jsonl"))):
            with open(f) as fh:
                for line in fh:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return logs


def load_llm_logs(date_str: str = None):
    """Load LLM call logs for a specific date."""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(LOG_DIR, f"llm_calls_{date_str}.jsonl")
    logs = []
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return logs


def list_llm_log_dates():
    """List available dates with LLM logs."""
    dates = []
    for f in sorted(glob.glob(os.path.join(LOG_DIR, "llm_calls_*.jsonl"))):
        # Extract date from filename: llm_calls_2026-02-14.jsonl
        basename = os.path.basename(f)
        date_part = basename.replace("llm_calls_", "").replace(".jsonl", "")
        dates.append(date_part)
    return dates


# Cost estimates per provider (USD per character)
# DeepSeek: $0.14/1M input + $0.28/1M output ≈ $0.21/1M chars avg
# ~4 chars per token → $0.21/1M chars
COST_PER_CHAR = {
    "google": 0,              # Gemini free tier
    "deepseek": 0.00000021,   # $0.21 per 1M chars
}


def aggregate_to_1h_ohlc(snapshots, coin):
    """Aggregate 5-minute snapshot ticks into 1-hour OHLC candles."""
    # Collect (ts, price) for this coin
    ticks = []
    for snap in snapshots:
        cd = snap.get("coins", {}).get(coin)
        if cd:
            ticks.append((snap["ts"], cd["price"]))

    if len(ticks) < 2:
        return None

    # Group by hour: ts // 3600 → same bucket
    buckets = {}
    for ts, price in ticks:
        hour_key = ts // 3600
        buckets.setdefault(hour_key, []).append((ts, price))

    if len(buckets) < 2:
        return None

    # Build OHLC per bucket
    candles = []
    for hour_key in sorted(buckets):
        pts = buckets[hour_key]
        pts.sort(key=lambda x: x[0])  # sort by time
        prices = [p for _, p in pts]
        candles.append({
            "ts": hour_key * 3600,  # clean hour boundary
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
        })

    return candles


# ─── Load Data ───
memory = load_memory()
decisions = memory["decisions"]
agent_stats = memory["agent_stats"]
trade_logs = load_trade_logs()

# ─── Header ───
st.title("🦈 Leviathan Trading Monitor")
st.caption("Phase 5 — TradingAgents Simple System")

# ─── Tabs ───
tab_trading, tab_watcher, tab_llm = st.tabs(["🦈 Trading Monitor", "📡 Market Watcher", "🤖 LLM Usage"])

# ══════════════════════════════════════════════════════════════
# Tab 1: Trading Monitor (original content)
# ══════════════════════════════════════════════════════════════
with tab_trading:
    # ─── Quick Actions ───
    if not st.session_state["analysis_running"]:
        # ── Idle: show Run form ──
        with st.expander("🚀 Run Analysis", expanded=False):
            qa_left, qa_right = st.columns([2, 1])
            with qa_left:
                run_tickers = st.text_input("Ticker(s)", value="BTC",
                                            help="Space-separated, e.g. BTC ETH")
            with qa_right:
                run_mode = st.selectbox("Mode", ["dry", "paper"], index=0)
                run_rounds = st.number_input("Debate rounds", min_value=1, max_value=5, value=2)

            if st.button("▶ Run Analysis", type="primary"):
                tickers = run_tickers.strip().split()
                if not tickers:
                    st.error("Enter at least one ticker.")
                else:
                    st.session_state["analysis_running"] = True
                    st.session_state["analysis_tickers"] = tickers
                    st.session_state["analysis_mode"] = run_mode
                    st.session_state["analysis_rounds"] = run_rounds
                    st.rerun()

        # Show last report if exists
        if st.session_state.get("last_report"):
            report = st.session_state["last_report"]
            with st.expander(report["title"], expanded=False):
                rep_cols = st.columns(4)
                rep_cols[0].metric("Duration", f"{report['elapsed']:.0f}s")
                rep_cols[1].metric("API Calls", f"~{report['api_total']}")
                rep_cols[2].metric("Fallbacks", report["fallbacks"])
                rep_cols[3].metric("Breaker Skips", report["breaker_skips"])
                if report.get("providers_str"):
                    st.caption(f"Providers: {report['providers_str']}")
                if report["breaker_skips"] > 0:
                    st.info(f"🔒 Circuit breaker saved ~{report['breaker_skips'] * 3}s")
                with st.expander("📜 Full Output"):
                    st.code(report["output"], language="text")

    else:
        # ── Running: show progress + stop ──
        import subprocess, time as _time

        tickers = st.session_state.get("analysis_tickers", ["BTC"])
        run_mode = st.session_state.get("analysis_mode", "dry")
        run_rounds = st.session_state.get("analysis_rounds", 2)

        st.status(f"🔄 Analyzing {', '.join(tickers)} — mode: {run_mode}, rounds: {run_rounds}",
                  expanded=True, state="running")

        if st.button("🛑 Stop Analysis", type="secondary"):
            pid = st.session_state.get("analysis_pid")
            if pid:
                import signal as _signal
                try:
                    os.killpg(pid, _signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
            st.session_state["analysis_running"] = False
            st.session_state["last_report"] = {
                "title": "🛑 Stopped by user",
                "elapsed": 0, "api_total": 0, "fallbacks": 0,
                "breaker_skips": 0, "providers_str": "", "output": "Stopped.",
            }
            st.rerun()

        cmd = (f"cd {os.path.dirname(__file__)} && "
               f"source .venv/bin/activate && "
               f"python prod_trader.py {' '.join(tickers)} "
               f"--broker {run_mode} --rounds {run_rounds} 2>&1")

        stages = [
            ("Production Trader", 0.05, "Initializing..."),
            ("Fetching", 0.10, "Fetching data..."),
            ("Sentiment", 0.20, "Sentiment analysis..."),
            ("Technical", 0.25, "Technical analysis..."),
            ("Fundamental", 0.30, "Fundamental analysis..."),
            ("consensus", 0.35, "Building consensus..."),
            ("context loaded", 0.40, "Market context..."),
            ("Bull vs Bear", 0.45, "Starting debate..."),
            ("Bull arguing", 0.55, "🐂 Bull arguing..."),
            ("Bear rebutting", 0.65, "🐻 Bear rebutting..."),
            ("Round 2", 0.70, "Round 2..."),
            ("Judge deliberating", 0.80, "⚖️ Judge deciding..."),
            ("Winner:", 0.85, "Winner decided!"),
            ("Risk:", 0.90, "Risk check..."),
            ("ALERT:", 0.93, "Alert sent..."),
            ("Memory #", 0.97, "Saving..."),
        ]

        api_summary = {"total": 0, "fallback": 0, "breaker_skip": 0, "providers": {}}

        progress_bar = st.progress(0, text="Starting...")
        timer_text = st.empty()
        log_area = st.empty()
        t0 = _time.time()
        output_lines = []
        current_pct = 0

        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, executable="/bin/bash", bufsize=1,
            preexec_fn=lambda: __import__('os').setpgrp(),
        )
        st.session_state["analysis_pid"] = proc.pid

        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            output_lines.append(line)
            elapsed = _time.time() - t0

            # Track API usage
            if "Fallback →" in line:
                api_summary["total"] += 1
                api_summary["fallback"] += 1
            elif "Circuit breaker OPEN →" in line:
                api_summary["total"] += 1
                api_summary["breaker_skip"] += 1

            if "→ deepseek" in line:
                api_summary["providers"]["deepseek"] = api_summary["providers"].get("deepseek", 0) + 1
            elif "→ google" in line:
                api_summary["providers"]["google"] = api_summary["providers"].get("google", 0) + 1

            # Update progress
            for keyword, pct, label in stages:
                if keyword in line and pct > current_pct:
                    current_pct = pct
                    break
            else:
                label = None

            progress_bar.progress(current_pct, text=f"{current_pct:.0%} — {label or line[:60]}")
            timer_text.caption(f"⏱ {elapsed:.0f}s elapsed")
            log_area.code("\n".join(output_lines[-12:]), language="text")

        proc.wait()
        elapsed = _time.time() - t0

        # Build report
        providers_str = " | ".join(
            f"{'🟢' if p == 'google' else '🔵'} {p}: {c}"
            for p, c in api_summary["providers"].items()
        )

        if proc.returncode == 0:
            progress_bar.progress(1.0, text="✅ 100% — Complete!")
            title = f"✅ Analysis complete — {elapsed:.0f}s"
        else:
            title = f"❌ Failed (exit {proc.returncode}) — {elapsed:.0f}s"

        st.session_state["last_report"] = {
            "title": title,
            "elapsed": elapsed,
            "api_total": api_summary["total"],
            "fallbacks": api_summary["fallback"],
            "breaker_skips": api_summary["breaker_skip"],
            "providers_str": providers_str,
            "output": "\n".join(output_lines),
        }

        st.session_state["analysis_running"] = False
        st.session_state.pop("analysis_pid", None)
        st.rerun()  # Rerun to show idle state with report

    # ─── Metrics Row ───
    col1, col2, col3, col4, col5 = st.columns(5)

    total = len(decisions)
    evaluated = [d for d in decisions if d.get("outcome")]
    correct = [d for d in evaluated if d["outcome"].get("correct")]
    accuracy = len(correct) / len(evaluated) if evaluated else 0

    col1.metric("Total Decisions", total)
    col2.metric("Evaluated", len(evaluated))
    col3.metric("Correct", len(correct))
    col4.metric("Accuracy", f"{accuracy:.0%}")
    col5.metric("Agents Tracked", len(agent_stats))

    st.divider()

    # ─── Two Column Layout ───
    left, right = st.columns([2, 1])

    with left:
        st.subheader("📜 Decision History")

        if decisions:
            for d in reversed(decisions):
                icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(d["decision"], "⚪")
                winner_icon = {"bull": "🐂", "bear": "🐻", "tie": "🤝"}.get(d.get("winner", ""), "")

                outcome_text = "⏳ Pending"
                if d.get("outcome"):
                    oc = d["outcome"]
                    ok = "✅" if oc["correct"] else "❌"
                    outcome_text = f"{ok} {oc['pct_change']:+.1f}% → ${oc['price_now']:.2f}"

                with st.expander(
                    f"{icon} #{d['id']} {d['ticker']} — {d['decision']} "
                    f"({d['confidence']:.0%}) @ ${d['price_at_decision']:.2f}  |  {outcome_text}",
                    expanded=False,
                ):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Date:** {d['date']}")
                        st.write(f"**Mode:** {d.get('mode', 'N/A')}")
                        st.write(f"**Winner:** {winner_icon} {d.get('winner', 'N/A')}")
                    with c2:
                        st.write(f"**Confidence:** {d['confidence']:.0%}")
                        st.write(f"**Outcome:** {outcome_text}")

                    if d.get("agent_views"):
                        st.write("**Agent Views:**")
                        for av in d["agent_views"]:
                            view_icon = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(av["view"], "⚪")
                            st.write(f"  {view_icon} {av['agent']}: {av['view']} ({av['confidence']:.0%})")
        else:
            st.info("No decisions yet. Run `python prod_trader.py NVDA` to generate data.")

    with right:
        st.subheader("🧠 Agent Performance")

        if agent_stats:
            for agent, stats in sorted(agent_stats.items(), key=lambda x: x[1]["accuracy"], reverse=True):
                acc = stats["accuracy"]
                st.markdown(f"**{agent}**")
                st.progress(acc, text=f"{acc:.0%} ({stats['correct']}/{stats['total']})")
        else:
            st.info("No agent stats yet. Run `python prod_trader.py --evaluate` first.")

        st.subheader("📊 Decision Distribution")

        if decisions:
            buy_count = sum(1 for d in decisions if d["decision"] == "BUY")
            sell_count = sum(1 for d in decisions if d["decision"] == "SELL")
            hold_count = sum(1 for d in decisions if d["decision"] == "HOLD")

            fig = go.Figure(data=[go.Pie(
                labels=["BUY", "SELL", "HOLD"],
                values=[buy_count, sell_count, hold_count],
                marker_colors=["#00cc66", "#ff4444", "#ffaa00"],
                hole=0.4,
            )])
            fig.update_layout(
                height=250,
                margin=dict(t=20, b=20, l=20, r=20),
                showlegend=True,
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 By Ticker")

        if decisions:
            tickers = {}
            for d in decisions:
                t = d["ticker"]
                if t not in tickers:
                    tickers[t] = {"count": 0, "buys": 0, "sells": 0, "holds": 0}
                tickers[t]["count"] += 1
                tickers[t][{"BUY": "buys", "SELL": "sells", "HOLD": "holds"}[d["decision"]]] += 1

            for ticker, info in tickers.items():
                st.write(f"**{ticker}** — {info['count']} decisions: "
                         f"🟢{info['buys']} 🔴{info['sells']} 🟡{info['holds']}")

    st.divider()

    st.subheader("🔔 Recent Trade Alerts")

    if trade_logs:
        for log in reversed(trade_logs[-10:]):
            icon = log.get("icon", "⚪")
            approved = "✅" if log.get("risk_approved") else "🚫"
            executed = "📤" if log.get("executed") else ""

            st.write(
                f"{icon} **{log.get('ticker', '?')}** → {log.get('action', '?')} "
                f"({log.get('confidence', 0):.0%}) @ ${log.get('price', 0):.2f} "
                f"| {approved} {log.get('shares', 0)} shares "
                f"(${log.get('position_size', 0):.2f}) {executed}"
            )
    else:
        st.info("No trade alerts yet.")

# ══════════════════════════════════════════════════════════════
# Tab 2: Market Watcher
# ══════════════════════════════════════════════════════════════
with tab_watcher:
    # ─── Controls ───
    ctrl_left, ctrl_right = st.columns([1, 2])

    with ctrl_left:
        selected_date = st.date_input("Date", value=date_type.today())
        date_str = selected_date.strftime("%Y-%m-%d")

    with ctrl_right:
        watchlist = load_watchlist()
        selected_coins = st.multiselect("Coins", options=watchlist, default=watchlist)

    # ─── Load watcher data ───
    snapshots = read_jsonl(snapshot_path(date_str))
    events = read_jsonl(event_path(date_str))

    if not snapshots:
        st.warning(f"No watcher data for {date_str}. Run `python watcher.py --tick` to start collecting.")
    else:
        last_snap = snapshots[-1]

        # ─── Metric cards per coin ───
        st.subheader("📊 Current Prices")
        cols = st.columns(min(len(selected_coins), 4) or 1)
        for i, coin in enumerate(selected_coins):
            coin_data = last_snap.get("coins", {}).get(coin)
            if not coin_data:
                continue
            with cols[i % len(cols)]:
                change = coin_data.get("change_24h", 0)
                st.metric(
                    label=coin,
                    value=f"฿{coin_data['price']:,.2f}",
                    delta=f"{change:+.2f}%",
                )

        # ─── Price Line Chart ───
        st.subheader("📈 Price Ticks")
        for coin in selected_coins:
            times = []
            prices = []
            for snap in snapshots:
                cd = snap.get("coins", {}).get(coin)
                if cd:
                    times.append(datetime.fromtimestamp(snap["ts"]))
                    prices.append(cd["price"])
            if not times:
                continue

            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=times, y=prices, mode="lines+markers",
                name=coin, line=dict(width=2),
            ))
            fig_line.update_layout(
                title=f"{coin} — {date_str}",
                xaxis_title="Time", yaxis_title="Price (THB)",
                height=350, margin=dict(t=40, b=30, l=50, r=20),
            )
            st.plotly_chart(fig_line, use_container_width=True)

        # ─── 1-Hour Candlestick Chart ───
        st.subheader("🕯️ 1-Hour Candles")
        for coin in selected_coins:
            candles = aggregate_to_1h_ohlc(snapshots, coin)
            if not candles:
                st.caption(f"{coin}: Not enough data for candles (need 2+ hours of ticks)")
                continue

            fig_candle = go.Figure(data=[go.Candlestick(
                x=[datetime.fromtimestamp(c["ts"]) for c in candles],
                open=[c["open"] for c in candles],
                high=[c["high"] for c in candles],
                low=[c["low"] for c in candles],
                close=[c["close"] for c in candles],
                name=coin,
            )])
            fig_candle.update_layout(
                title=f"{coin} — 1H Candles",
                xaxis_title="Hour", yaxis_title="Price (THB)",
                xaxis_rangeslider_visible=False,
                height=400, margin=dict(t=40, b=30, l=50, r=20),
            )
            st.plotly_chart(fig_candle, use_container_width=True)

        # ─── Event Log ───
        st.subheader("⚡ Events")
        coin_events = [e for e in events if e.get("coin") in selected_coins]
        if coin_events:
            df = pd.DataFrame(coin_events)
            display_cols = [c for c in ["time", "coin", "type", "magnitude", "description"] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        else:
            st.caption("No events detected today.")

        # ─── Market Context Summary ───
        st.subheader("🧠 Market Context")
        ctx = MarketContext.load_today(date_str)
        if ctx:
            st.write(f"**Sentiment:** {ctx.get('market_sentiment', 'N/A')} "
                     f"| **Snapshots:** {ctx.get('snapshot_count', 0)}")
            for coin in selected_coins:
                coin_ctx = ctx.get("coins", {}).get(coin)
                if coin_ctx:
                    st.markdown(
                        f"**{coin}** — {coin_ctx.get('regime', '?')} | "
                        f"Volatility: {coin_ctx.get('volatility', '?')} | "
                        f"Change: {coin_ctx.get('change_pct', 0):+.2f}%"
                    )
                    if coin_ctx.get("summary"):
                        st.caption(coin_ctx["summary"])
        else:
            st.caption("No context available. Need more snapshots.")

# ══════════════════════════════════════════════════════════════
# Tab 3: LLM Usage
# ══════════════════════════════════════════════════════════════
with tab_llm:
    # ─── Date selector ───
    llm_date_col, llm_info_col = st.columns([1, 3])
    with llm_date_col:
        llm_selected_date = st.date_input("Date", value=date_type.today(), key="llm_date")
        llm_date_str = llm_selected_date.strftime("%Y-%m-%d")

    llm_logs = load_llm_logs(llm_date_str)

    with llm_info_col:
        st.caption(f"Showing logs for **{llm_date_str}** | {len(llm_logs)} API calls")

    if not llm_logs:
        st.warning(f"No LLM calls on {llm_date_str}. Run analysis to generate data.")
    else:
        # ─── Count analysis sessions (gap > 60s between calls = new session) ───
        session_count = 1
        for i in range(1, len(llm_logs)):
            try:
                t_prev = datetime.fromisoformat(llm_logs[i-1]["ts"])
                t_curr = datetime.fromisoformat(llm_logs[i]["ts"])
                if (t_curr - t_prev).total_seconds() > 60:
                    session_count += 1
            except (KeyError, ValueError):
                pass

        # ─── Summary metrics ───
        total_calls = len(llm_logs)
        success_calls = sum(1 for l in llm_logs if l.get("success"))
        fallback_calls = sum(1 for l in llm_logs if l.get("fallback"))
        breaker_skips = sum(1 for l in llm_logs
                            if l.get("circuit_breaker", {}).get("state") == "open"
                            and l.get("fallback"))
        avg_latency = sum(l.get("latency_ms", 0) for l in llm_logs) / total_calls

        # Provider breakdown
        by_provider = {}
        for l in llm_logs:
            p = l.get("provider", "unknown")
            by_provider.setdefault(p, {"calls": 0, "chars_in": 0, "chars_out": 0})
            by_provider[p]["calls"] += 1
            by_provider[p]["chars_in"] += l.get("prompt_len", 0)
            by_provider[p]["chars_out"] += l.get("response_len", 0)

        # Estimated cost
        total_cost = 0
        for p, stats in by_provider.items():
            rate = COST_PER_CHAR.get(p, 0)
            total_cost += (stats["chars_in"] + stats["chars_out"]) * rate

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Analysis Runs", session_count)
        c2.metric("API Calls", total_calls)
        c3.metric("Success", f"{success_calls}/{total_calls}")
        c4.metric("Fallbacks", fallback_calls,
                  help=f"Tried primary & failed: {fallback_calls - breaker_skips} | "
                       f"Skipped by circuit breaker: {breaker_skips}")
        c5.metric("Avg Latency", f"{avg_latency:.0f}ms")
        c6.metric("Est. Cost", f"${total_cost:.4f}")

        st.divider()

        # ─── Provider breakdown ───
        st.subheader("📊 Provider Breakdown")
        prov_left, prov_right = st.columns(2)

        with prov_left:
            fig_prov = go.Figure(data=[go.Pie(
                labels=list(by_provider.keys()),
                values=[s["calls"] for s in by_provider.values()],
                marker_colors=["#4285f4", "#0f9d58", "#f4b400", "#db4437"],
                hole=0.4,
            )])
            fig_prov.update_layout(
                title="Calls by Provider",
                height=280, margin=dict(t=40, b=20, l=20, r=20),
            )
            st.plotly_chart(fig_prov, use_container_width=True)

        with prov_right:
            for p, stats in by_provider.items():
                rate = COST_PER_CHAR.get(p, 0)
                cost = (stats["chars_in"] + stats["chars_out"]) * rate
                icon = "🟢" if p == "google" else "🔵" if p == "deepseek" else "⚪"
                st.markdown(f"**{icon} {p.title()}**")
                st.write(f"  Calls: **{stats['calls']}** | "
                         f"Input: {stats['chars_in']:,} chars | "
                         f"Output: {stats['chars_out']:,} chars")
                st.write(f"  Est. cost: **${cost:.4f}**")

            # Circuit breaker status from latest log entry
            last_breaker = None
            for l in reversed(llm_logs):
                if l.get("circuit_breaker"):
                    last_breaker = l["circuit_breaker"]
                    break
            if last_breaker:
                state = last_breaker.get("state", "?")
                state_icon = {"closed": "🟢", "open": "🔴", "half_open": "🟡"}.get(state, "⚪")
                st.markdown(f"**Circuit Breaker:** {state_icon} {state.upper()}")
                if last_breaker.get("last_error"):
                    st.caption(f"Last error: {last_breaker['last_error'][:80]}")

        st.divider()

        # ─── Call timeline ───
        st.subheader("📈 Calls per Hour")
        timeline = {}
        for l in llm_logs:
            try:
                ts = datetime.fromisoformat(l["ts"])
                hour_key = ts.strftime("%H:00")
                timeline.setdefault(hour_key, {"google": 0, "deepseek": 0})
                p = l.get("provider", "unknown")
                if p in timeline[hour_key]:
                    timeline[hour_key][p] += 1
            except (KeyError, ValueError):
                pass

        if timeline:
            hours = sorted(timeline.keys())
            fig_timeline = go.Figure()
            for provider, color in [("google", "#4285f4"), ("deepseek", "#0f9d58")]:
                fig_timeline.add_trace(go.Bar(
                    x=hours,
                    y=[timeline[h].get(provider, 0) for h in hours],
                    name=provider.title(),
                    marker_color=color,
                ))
            fig_timeline.update_layout(
                barmode="stack", height=300,
                margin=dict(t=20, b=30, l=50, r=20),
                xaxis_title="Hour", yaxis_title="Calls",
            )
            st.plotly_chart(fig_timeline, use_container_width=True)

        # ─── Call log table ───
        st.subheader("📋 Call Log")
        df = pd.DataFrame(llm_logs)
        if "ts" in df.columns:
            df["time"] = df["ts"].apply(
                lambda x: x.split("T")[1][:8] if "T" in str(x) else x)
        display_cols = [c for c in ["time", "provider", "model", "fallback", "success",
                                     "prompt_len", "response_len", "latency_ms", "error"]
                        if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

# ─── Footer ───
st.divider()
foot_left, foot_right = st.columns([3, 1])
with foot_left:
    st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
with foot_right:
    if st.button("🔄 Refresh", key="manual_refresh"):
        st.rerun()

