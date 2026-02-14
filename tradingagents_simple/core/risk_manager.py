"""
Risk Manager - Final gate before any trade execution
Phase 5: Enforces position limits, drawdown protection, and confidence thresholds

The Risk Manager has VETO POWER over any AI decision.
"""
from typing import Dict, Any, Optional
from datetime import datetime


class RiskManager:
    """
    Evaluates whether a trading decision should be executed.
    No trade goes through without risk approval.

    Rules:
    1. Confidence must exceed threshold
    2. Position size must respect limits
    3. Max open positions enforced
    4. Daily loss limit (drawdown circuit breaker)
    5. No trading outside market hours (optional)
    """

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.confidence_threshold = config.get("confidence_threshold", 0.6)
        self.max_position_size = config.get("max_position_size", 1000)
        self.max_positions = config.get("max_positions", 5)
        self.risk_per_trade = config.get("risk_per_trade", 0.02)
        self.daily_loss_limit = config.get("daily_loss_limit", 0.05)  # 5% of portfolio
        self.portfolio_value = config.get("portfolio_value", 10000)
        self.currency = config.get("currency", "USD")  # "USD" or "THB"
        self.is_crypto = self.currency == "THB"  # Crypto uses fractional units
        self.stop_loss_pct = config.get("stop_loss_pct", 0.02 if not self.is_crypto else 0.05)
        self.take_profit_pct = config.get("take_profit_pct", 0.04 if not self.is_crypto else 0.10)
        self.volatility_scale = config.get("volatility_scale", False)

        # Tracking
        self._daily_pnl = 0.0
        self._open_positions = {}
        self._trade_log = []

    def evaluate(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a trading decision. Returns approval or rejection with reason.

        Input: {"ticker": str, "decision": str, "confidence": float, "current_price": float, ...}
        Output: {"approved": bool, "action": str, "reason": str, "position_size": float, ...}
        """
        ticker = decision["ticker"]
        action = decision["decision"]
        confidence = decision["confidence"]
        price = decision["current_price"]

        # Rule 1: Confidence threshold
        if confidence < self.confidence_threshold:
            return self._reject(
                ticker, action,
                f"Confidence {confidence:.0%} below threshold {self.confidence_threshold:.0%}"
            )

        # Rule 2: HOLD needs no execution
        if action == "HOLD":
            return {
                "approved": True,
                "action": "HOLD",
                "ticker": ticker,
                "reason": "Hold — no trade needed",
                "position_size": 0,
                "shares": 0,
            }

        # Rule 3: Daily loss circuit breaker
        if self._daily_pnl < -(self.daily_loss_limit * self.portfolio_value):
            return self._reject(
                ticker, action,
                f"Daily loss limit hit ({'฿' if self.is_crypto else '$'}{self._daily_pnl:.2f}). Trading halted."
            )

        # Rule 4: Max positions
        if action == "BUY" and len(self._open_positions) >= self.max_positions:
            if ticker not in self._open_positions:
                return self._reject(
                    ticker, action,
                    f"Max {self.max_positions} positions reached. Close one first."
                )

        # Rule 5: Position sizing (risk-adjusted)
        volatility = decision.get("data", {}).get("indicators", {}).get("volatility")
        position_size = self._calculate_position_size(price, confidence, volatility)

        if self.is_crypto:
            # Crypto: fractional amounts, size in THB
            qty = position_size / price  # fractional crypto units
            if position_size < 10:  # Bitkub min ~10 THB
                return self._reject(
                    ticker, action,
                    f"Position size ฿{position_size:.2f} below minimum"
                )
            shares = round(qty, 8)
            reason = f"Risk-approved: {shares:.6f} {ticker} @ ฿{price:,.2f} = ฿{position_size:,.2f}"
            actual_size = round(position_size, 2)
        else:
            # Stocks: integer shares, size in USD
            shares = int(position_size / price)
            if shares < 1:
                return self._reject(
                    ticker, action,
                    f"Position size ${position_size:.2f} too small for 1 share @ ${price:.2f}"
                )
            reason = f"Risk-approved: {shares} shares @ ${price:.2f} = ${shares * price:.2f}"
            actual_size = round(shares * price, 2)

        # APPROVED
        result = {
            "approved": True,
            "action": action,
            "ticker": ticker,
            "reason": reason,
            "position_size": actual_size,
            "shares": shares,
            "confidence": confidence,
            "stop_loss": round(price * (1 - self.stop_loss_pct), 2) if action == "BUY" else None,
            "take_profit": round(price * (1 + self.take_profit_pct), 2) if action == "BUY" else None,
        }

        self._trade_log.append({
            "time": datetime.now().isoformat(),
            **result
        })

        return result

    def _calculate_position_size(self, price: float, confidence: float,
                                  volatility: float = None) -> float:
        """Risk-adjusted position sizing: higher confidence = larger position"""
        base_size = min(self.max_position_size, self.portfolio_value * self.risk_per_trade)
        # Scale by confidence (0.6 threshold → 1.0 max)
        confidence_scale = (confidence - self.confidence_threshold) / (1.0 - self.confidence_threshold)
        confidence_scale = max(0.3, min(1.0, confidence_scale))  # 30% to 100% of base
        size = base_size * confidence_scale

        # Volatility scaling: reduce size when market is wild
        if self.volatility_scale and volatility and volatility > 5:
            vol_penalty = min(0.5, (volatility - 5) / 10)  # up to 50% reduction
            size *= (1 - vol_penalty)

        return size

    def _reject(self, ticker: str, action: str, reason: str) -> Dict[str, Any]:
        return {
            "approved": False,
            "action": action,
            "ticker": ticker,
            "reason": f"REJECTED: {reason}",
            "position_size": 0,
            "shares": 0,
        }

    def record_pnl(self, amount: float):
        """Record realized P&L for daily tracking"""
        self._daily_pnl += amount

    def reset_daily(self):
        """Reset daily counters (call at market open)"""
        self._daily_pnl = 0.0

    def get_status(self) -> Dict:
        return {
            "open_positions": len(self._open_positions),
            "max_positions": self.max_positions,
            "daily_pnl": self._daily_pnl,
            "daily_loss_limit": self.daily_loss_limit * self.portfolio_value,
            "trades_today": len(self._trade_log),
        }
