"""
Alert System - Notifications for trading decisions
Phase 5: Console, file logging, and Telegram notifications
"""
import os
import json
from typing import Dict, Any, List
from datetime import datetime


class AlertManager:
    """
    Sends trading alerts through multiple channels.
    Channels: console (always), file log, telegram (optional)
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        self.channels = config.get("channels", ["console", "file"])
        self.log_dir = config.get("log_dir", os.path.join(
            os.path.dirname(__file__), "..", "data", "logs"
        ))
        self.telegram_token = config.get("telegram_token") or os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = config.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")
        os.makedirs(self.log_dir, exist_ok=True)

    def send(self, decision: Dict, risk_result: Dict, execution: Dict = None):
        """Send alert for a trading event"""
        alert = self._build_alert(decision, risk_result, execution)

        if "console" in self.channels:
            self._console_alert(alert)
        if "file" in self.channels:
            self._file_alert(alert)
        if "telegram" in self.channels and self.telegram_token:
            self._telegram_alert(alert)

    def _build_alert(self, decision: Dict, risk: Dict, execution: Dict) -> Dict:
        icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
        action = decision.get("decision", "HOLD")

        alert = {
            "timestamp": datetime.now().isoformat(),
            "ticker": decision["ticker"],
            "action": action,
            "icon": icon.get(action, "⚪"),
            "confidence": decision.get("confidence", 0),
            "price": decision.get("current_price", 0),
            "risk_approved": risk.get("approved", False),
            "risk_reason": risk.get("reason", ""),
            "shares": risk.get("shares", 0),
            "position_size": risk.get("position_size", 0),
            "currency": decision.get("data", {}).get("currency", "$"),
        }

        if execution:
            alert["executed"] = execution.get("executed", False)
            alert["order_id"] = execution.get("order_id", "")
            alert["exec_mode"] = execution.get("mode", "")

        return alert

    def _console_alert(self, alert: Dict):
        """Print rich console alert"""
        line = (
            f"\n  {alert['icon']} ALERT: {alert['ticker']} → {alert['action']} "
            f"({alert['confidence']:.0%}) @ {alert['currency']}{alert['price']:,.2f}"
        )
        if alert["risk_approved"]:
            line += f" | {alert['shares']} shares ({alert['currency']}{alert['position_size']:,.2f})"
        else:
            line += f" | {alert['risk_reason']}"
        if alert.get("executed"):
            line += f" | Executed [{alert['exec_mode']}] #{alert.get('order_id', '')}"
        print(line)

    def _file_alert(self, alert: Dict):
        """Append to daily log file"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"trades_{date_str}.jsonl")
        with open(log_file, "a") as f:
            f.write(json.dumps(alert, default=str) + "\n")

    def _telegram_alert(self, alert: Dict):
        """Send Telegram notification"""
        if not self.telegram_token or not self.telegram_chat_id:
            return

        text = (
            f"{alert['icon']} *{alert['ticker']}* → {alert['action']}\n"
            f"Confidence: {alert['confidence']:.0%}\n"
            f"Price: {alert['currency']}{alert['price']:,.2f}\n"
        )
        if alert["risk_approved"]:
            text += f"Shares: {alert['shares']} ({alert['currency']}{alert['position_size']:,.2f})\n"
        if alert.get("executed"):
            text += f"Executed: {alert['exec_mode']} #{alert.get('order_id', '')}"

        try:
            import requests
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            requests.post(url, json={
                "chat_id": self.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=5)
        except Exception:
            pass  # Don't crash on notification failure
