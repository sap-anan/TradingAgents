#!/bin/bash
# ─── Daily Dry-Run Script ────────────────────────────────────────
# Runs watchlist coins through the full AI pipeline and logs results.
# Crypto trades 24/7 so this can run any time.
#
# Usage:
#   ./daily_run.sh              # Run watchlist (default)
#   ./daily_run.sh BTC ETH      # Run specific coins
#   crontab -e → add:
#     0 9 * * * /home/sap-anan/projects/TradingAgents/tradingagents_simple/daily_run.sh
# ──────────────────────────────────────────────────────────────────

set -e

# Config
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
LOG_DIR="$SCRIPT_DIR/data/logs"
DAILY_LOG="$LOG_DIR/daily_$(date +%Y-%m-%d).log"

# Ensure dirs
mkdir -p "$LOG_DIR"

# Activate venv
source "$VENV_DIR/bin/activate"
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════════════════════════" | tee -a "$DAILY_LOG"
echo "  🦈 Daily Dry-Run — $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$DAILY_LOG"
echo "═══════════════════════════════════════════════════════════" | tee -a "$DAILY_LOG"

# Step 1: Evaluate past decisions (check if yesterday's calls were right)
echo "" | tee -a "$DAILY_LOG"
echo "── Step 1: Evaluating past decisions ──" | tee -a "$DAILY_LOG"
python3 bitkub_trader.py --evaluate 2>&1 | tee -a "$DAILY_LOG"

# Step 2: Run analysis on coins
echo "" | tee -a "$DAILY_LOG"
echo "── Step 2: Analyzing coins ──" | tee -a "$DAILY_LOG"

if [ $# -gt 0 ]; then
    # Specific coins from command line
    COINS="$@"
    echo "Coins (CLI): $COINS" | tee -a "$DAILY_LOG"
    python3 bitkub_trader.py $COINS --rounds 2 2>&1 | tee -a "$DAILY_LOG"
else
    # Use watchlist
    WATCHLIST=$(python3 -c "
import json, os
f = os.path.join('data', 'watchlist.json')
if os.path.exists(f):
    print(' '.join(json.load(open(f))))
else:
    print('')
" 2>/dev/null)

    if [ -z "$WATCHLIST" ]; then
        echo "No watchlist found. Add coins: python3 bitkub_trader.py --watchlist-add BTC ETH SOL" | tee -a "$DAILY_LOG"
        exit 1
    fi

    echo "Watchlist: $WATCHLIST" | tee -a "$DAILY_LOG"
    python3 bitkub_trader.py $WATCHLIST --rounds 2 2>&1 | tee -a "$DAILY_LOG"
fi

# Step 3: Show agent stats
echo "" | tee -a "$DAILY_LOG"
echo "── Step 3: Agent stats ──" | tee -a "$DAILY_LOG"
python3 bitkub_trader.py --stats 2>&1 | tee -a "$DAILY_LOG"

# Step 4: Quick market scan
echo "" | tee -a "$DAILY_LOG"
echo "── Step 4: Market scan (top 5) ──" | tee -a "$DAILY_LOG"
python3 bitkub_trader.py --scan 5 2>&1 | tee -a "$DAILY_LOG"

echo "" | tee -a "$DAILY_LOG"
echo "═══════════════════════════════════════════════════════════" | tee -a "$DAILY_LOG"
echo "  Done: $(date '+%H:%M:%S') | Log: $DAILY_LOG" | tee -a "$DAILY_LOG"
echo "═══════════════════════════════════════════════════════════" | tee -a "$DAILY_LOG"
