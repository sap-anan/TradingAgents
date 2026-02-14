"""Technical indicators computed from price series."""
from typing import List


def rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    Relative Strength Index (Wilder's smoothing).

    Args:
        prices: List of closing prices (oldest first).
        period: RSI lookback period (default 14).

    Returns:
        List of RSI values, length = len(prices) - period.
        Empty list if insufficient data.
    """
    if len(prices) < period + 1:
        return []

    deltas = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]

    # Seed: simple average of first `period` deltas
    gains = [max(d, 0) for d in deltas[:period]]
    losses = [abs(min(d, 0)) for d in deltas[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    results = []
    # First RSI value
    if avg_loss == 0:
        results.append(100.0 if avg_gain > 0 else 50.0)
    else:
        rs = avg_gain / avg_loss
        results.append(100.0 - (100.0 / (1.0 + rs)))

    # Subsequent values: Wilder's smoothing
    for i in range(period, len(deltas)):
        d = deltas[i]
        gain = max(d, 0)
        loss = abs(min(d, 0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            results.append(100.0 if avg_gain > 0 else 50.0)
        else:
            rs = avg_gain / avg_loss
            results.append(100.0 - (100.0 / (1.0 + rs)))

    return results
