"""
Broker Interface - Connects to Alpaca for paper/live trading
Phase 5: Execute trades through a real broker API

Supports:
- Paper trading (default, safe) via Alpaca
- Dry-run mode (no broker needed, just logs)
"""
import os
from typing import Dict, Any, Optional
from datetime import datetime
from core.event_bus import EventBus


class BrokerInterface:
    """
    Broker abstraction layer. Supports:
    - "dry_run": No real orders, just prints what would happen (default)
    - "alpaca_paper": Alpaca paper trading (fake money, real API)
    - "alpaca_live": Alpaca live trading (REAL money — use with extreme caution)
    - "bitkub_dry": Bitkub dry run (logs THB-denominated crypto trades)
    - "bitkub_live": Bitkub live trading (REAL THB — use with extreme caution)
    """

    def __init__(self, mode: str = "dry_run", config: Dict = None):
        self.mode = mode
        self.config = config or {}
        self._client = None
        self._order_log = []

        if mode.startswith("alpaca"):
            self._init_alpaca()
        elif mode == "bitkub_live":
            self._init_bitkub()

    def _init_alpaca(self):
        """Initialize Alpaca client"""
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            api_key = self.config.get("api_key") or os.getenv("ALPACA_API_KEY")
            secret_key = self.config.get("secret_key") or os.getenv("ALPACA_SECRET_KEY")

            if not api_key or not secret_key:
                raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY required")

            paper = self.mode == "alpaca_paper"
            self._client = TradingClient(api_key, secret_key, paper=paper)
            self._modules = {
                "MarketOrderRequest": MarketOrderRequest,
                "OrderSide": OrderSide,
                "TimeInForce": TimeInForce,
            }
            print(f"  ✓ Alpaca {'paper' if paper else 'LIVE'} trading connected")
        except ImportError:
            print("  ⚠ alpaca-py not installed. Run: pip install alpaca-py")
            print("  → Falling back to dry_run mode")
            self.mode = "dry_run"

    def execute(self, risk_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a risk-approved trade.
        Input: output from RiskManager.evaluate()
        """
        if not risk_result["approved"]:
            return {"executed": False, "reason": risk_result["reason"]}

        if risk_result["action"] == "HOLD":
            return {"executed": False, "reason": "HOLD — no trade"}

        if self.mode == "dry_run" or self.mode == "bitkub_dry":
            return self._dry_run(risk_result)
        elif self.mode.startswith("alpaca"):
            return self._alpaca_execute(risk_result)
        elif self.mode == "bitkub_live":
            return self._bitkub_execute(risk_result)
        else:
            return {"executed": False, "reason": f"Unknown broker mode: {self.mode}"}

    def _dry_run(self, order: Dict) -> Dict[str, Any]:
        """Simulate trade execution (no real orders)"""
        result = {
            "executed": True,
            "mode": "dry_run",
            "ticker": order["ticker"],
            "action": order["action"],
            "shares": order["shares"],
            "position_size": order["position_size"],
            "stop_loss": order.get("stop_loss"),
            "take_profit": order.get("take_profit"),
            "timestamp": datetime.now().isoformat(),
            "order_id": f"DRY-{len(self._order_log) + 1:04d}",
        }
        self._order_log.append(result)
        EventBus.instance().emit("broker", "output", "order",
            {"action": order["action"], "ticker": order["ticker"], "shares": order["shares"]},
            status="ok")
        return result

    def _alpaca_execute(self, order: Dict) -> Dict[str, Any]:
        """Execute via Alpaca API"""
        if not self._client:
            return {"executed": False, "reason": "Alpaca client not initialized"}

        try:
            MarketOrderRequest = self._modules["MarketOrderRequest"]
            OrderSide = self._modules["OrderSide"]
            TimeInForce = self._modules["TimeInForce"]

            side = OrderSide.BUY if order["action"] == "BUY" else OrderSide.SELL
            req = MarketOrderRequest(
                symbol=order["ticker"],
                qty=order["shares"],
                side=side,
                time_in_force=TimeInForce.DAY,
            )

            response = self._client.submit_order(req)

            result = {
                "executed": True,
                "mode": self.mode,
                "ticker": order["ticker"],
                "action": order["action"],
                "shares": order["shares"],
                "order_id": str(response.id),
                "status": str(response.status),
                "timestamp": datetime.now().isoformat(),
            }
            self._order_log.append(result)
            return result

        except Exception as e:
            return {"executed": False, "reason": f"Alpaca error: {e}"}

    def _init_bitkub(self):
        """Initialize Bitkub client for live trading"""
        try:
            from core.bitkub_client import BitkubClient

            api_key = self.config.get("api_key") or os.getenv("BITKUB_API_KEY")
            api_secret = self.config.get("api_secret") or os.getenv("BITKUB_API_SECRET")

            if not api_key or not api_secret:
                raise ValueError("BITKUB_API_KEY and BITKUB_API_SECRET required")

            self._client = BitkubClient(api_key=api_key, api_secret=api_secret)
            # Test connection
            self._client.ticker(sym="THB_BTC")
            print("  ✓ Bitkub LIVE trading connected")
        except Exception as e:
            print(f"  ⚠ Bitkub init failed: {e}")
            print("  → Falling back to bitkub_dry mode")
            self.mode = "bitkub_dry"

    def _bitkub_execute(self, order: Dict) -> Dict[str, Any]:
        """Execute via Bitkub API"""
        if not self._client:
            return {"executed": False, "reason": "Bitkub client not initialized"}

        try:
            from core.bitkub_client import BitkubClient
            sym = BitkubClient.to_symbol(order["ticker"])

            if order["action"] == "BUY":
                # place_bid: amt in THB for market orders
                response = self._client.place_bid(
                    sym=sym,
                    amt=order["position_size"],
                    rat=0,
                    typ="market",
                )
            else:
                # place_ask: amt in crypto units
                # position_size is in THB, convert to crypto amount
                ticker_data = self._client.ticker(sym=sym)
                price = float(ticker_data.get(sym, {}).get("last", 0))
                if price <= 0:
                    return {"executed": False, "reason": f"Cannot get price for {sym}"}
                crypto_amt = order["position_size"] / price
                response = self._client.place_ask(
                    sym=sym,
                    amt=crypto_amt,
                    rat=0,
                    typ="market",
                )

            result = {
                "executed": True,
                "mode": "bitkub_live",
                "ticker": order["ticker"],
                "action": order["action"],
                "position_size": order["position_size"],
                "shares": order.get("shares", 0),
                "order_id": str(response.get("id", "unknown")),
                "timestamp": datetime.now().isoformat(),
                "currency": "THB",
            }
            self._order_log.append(result)
            return result

        except Exception as e:
            return {"executed": False, "reason": f"Bitkub error: {e}"}

    def get_portfolio(self) -> Optional[Dict]:
        """Get current portfolio from broker"""
        if self.mode in ("dry_run", "bitkub_dry"):
            return {
                "mode": self.mode,
                "orders": len(self._order_log),
                "note": "No real positions — dry run mode",
            }

        if self.mode == "bitkub_live" and self._client:
            try:
                balances = self._client.balances()
                # Filter non-zero balances
                non_zero = {k: v for k, v in balances.items()
                            if float(v.get("available", 0)) > 0 or float(v.get("reserved", 0)) > 0}
                return {
                    "mode": "bitkub_live",
                    "balances": non_zero,
                    "currency": "THB",
                }
            except Exception as e:
                return {"error": str(e)}

        if self._client:
            try:
                account = self._client.get_account()
                return {
                    "mode": self.mode,
                    "equity": float(account.equity),
                    "cash": float(account.cash),
                    "buying_power": float(account.buying_power),
                    "portfolio_value": float(account.portfolio_value),
                }
            except Exception as e:
                return {"error": str(e)}

        return None

    def get_order_log(self):
        return self._order_log
