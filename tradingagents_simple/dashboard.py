"""
Trading Dashboard - Streamlit monitoring UI
Reads from trading_memory.json and trade logs

Usage:
    streamlit run dashboard.py
"""
import streamlit as st
import json
import os
import glob
from datetime import datetime

# ─── Config ───
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "trading_memory.json")
LOG_DIR = os.path.join(DATA_DIR, "logs")

st.set_page_config(
    page_title="Leviathan Trading Monitor",
    page_icon="🦈",
    layout="wide",
)


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


# ─── Load Data ───
memory = load_memory()
decisions = memory["decisions"]
agent_stats = memory["agent_stats"]
trade_logs = load_trade_logs()

# ─── Header ───
st.title("🦈 Leviathan Trading Monitor")
st.caption("Phase 5 — TradingAgents Simple System")

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
    # ─── Decision History ───
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
    # ─── Agent Performance ───
    st.subheader("🧠 Agent Performance")

    if agent_stats:
        for agent, stats in sorted(agent_stats.items(), key=lambda x: x[1]["accuracy"], reverse=True):
            acc = stats["accuracy"]
            color = "green" if acc >= 0.6 else "orange" if acc >= 0.4 else "red"

            st.markdown(f"**{agent}**")
            st.progress(acc, text=f"{acc:.0%} ({stats['correct']}/{stats['total']})")
    else:
        st.info("No agent stats yet. Run `python prod_trader.py --evaluate` first.")

    # ─── Decision Distribution ───
    st.subheader("📊 Decision Distribution")

    if decisions:
        buy_count = sum(1 for d in decisions if d["decision"] == "BUY")
        sell_count = sum(1 for d in decisions if d["decision"] == "SELL")
        hold_count = sum(1 for d in decisions if d["decision"] == "HOLD")

        import plotly.graph_objects as go

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

    # ─── Ticker Breakdown ───
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

# ─── Trade Alerts Log ───
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

# ─── Footer ───
st.divider()
st.caption(
    f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    f"Data: {MEMORY_FILE} | "
    f"Auto-refresh: rerun page or use `st.rerun()`"
)
