import pytest
from core.indicators import rsi


def test_rsi_known_values():
    """RSI of flat prices should be 50 (no gains or losses)."""
    prices = [100.0] * 20
    result = rsi(prices, period=14)
    assert len(result) > 0
    assert result[-1] == pytest.approx(50.0, abs=0.1)


def test_rsi_all_up():
    """RSI of strictly increasing prices should be near 100."""
    prices = [float(i) for i in range(1, 30)]
    result = rsi(prices, period=14)
    assert result[-1] > 90


def test_rsi_all_down():
    """RSI of strictly decreasing prices should be near 0."""
    prices = [float(30 - i) for i in range(30)]
    result = rsi(prices, period=14)
    assert result[-1] < 10


def test_rsi_insufficient_data():
    """RSI with fewer than period+1 prices returns empty list."""
    prices = [100.0] * 10
    result = rsi(prices, period=14)
    assert result == []
