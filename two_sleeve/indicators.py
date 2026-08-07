"""Pure signal math. No I/O, no exchange calls — just lists of numbers in,
numbers out. Everything here is unit-tested in tests/test_indicators.py.

A note on style: each function takes plain Python sequences so you can paste
numbers in a REPL and see exactly what the bot sees. That is the point — this
project is for learning, and magic is the enemy of learning.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def sma(values: Sequence[float], period: int) -> float:
    """Simple moving average of the last `period` values."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError(f"need at least {period} values, got {len(values)}")
    window = values[-period:]
    return sum(window) / period


def ema(values: Sequence[float], period: int) -> float:
    """Exponential moving average, seeded with the SMA of the first window.

    EMA weights recent prices more heavily than old ones, so it turns faster
    than an SMA of the same period. Crossovers of a fast EMA over a slow EMA
    are the classic trend-following entry.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError(f"need at least {period} values, got {len(values)}")
    k = 2.0 / (period + 1.0)
    result = sum(values[:period]) / period
    for v in values[period:]:
        result = v * k + result * (1.0 - k)
    return result


def donchian(highs: Sequence[float], lows: Sequence[float], period: int) -> tuple[float, float]:
    """Donchian channel: (highest high, lowest low) over the last `period` bars.

    A close above the prior channel high is a breakout — the market just did
    something it hasn't done in `period` bars. Turtle-style trend systems are
    built on exactly this.
    """
    if len(highs) < period or len(lows) < period:
        raise ValueError(f"need at least {period} bars")
    return max(highs[-period:]), min(lows[-period:])


def true_range(high: float, low: float, prev_close: float) -> float:
    """True range of one bar: the bar's span, extended to cover any gap from
    the previous close."""
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float:
    """Average True Range (Wilder smoothing): the market's typical bar-to-bar
    movement in price units.

    ATR is how we size positions and place stops: a stop 2*ATR away is "outside
    normal noise", and risking a fixed dollar amount per trade means
    size = risk_dollars / stop_distance. Volatile market -> wider stop ->
    smaller position. That one idea is most of risk management.
    """
    n = len(closes)
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows, closes must be the same length")
    if n < period + 1:
        raise ValueError(f"need at least {period + 1} bars, got {n}")
    trs = [true_range(highs[i], lows[i], closes[i - 1]) for i in range(1, n)]
    value = sum(trs[:period]) / period
    for tr in trs[period:]:
        value = (value * (period - 1) + tr) / period
    return value


def rsi(closes: Sequence[float], period: int = 14) -> float:
    """Relative Strength Index (Wilder), 0-100.

    >70 is conventionally "overbought", <30 "oversold" — but in strong trends
    RSI can pin above 70 for weeks. We use it only as a *filter* (avoid buying
    a breakout that is already vertical), never as a standalone signal.
    """
    if len(closes) < period + 1:
        raise ValueError(f"need at least {period + 1} closes, got {len(closes)}")
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def zscore(values: Sequence[float], lookback: int) -> float:
    """How unusual is the latest value vs. the last `lookback` values, in
    standard deviations?

    We use this on funding rates: funding at z > +2 means longs are paying
    shorts an unusually large amount — a crowded-long tell.
    """
    if len(values) < lookback:
        raise ValueError(f"need at least {lookback} values, got {len(values)}")
    window = list(values[-lookback:])
    mean = sum(window) / len(window)
    var = sum((v - mean) ** 2 for v in window) / len(window)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return (window[-1] - mean) / std


def annualize_hourly_funding(hourly_rate: float) -> float:
    """Convert one hourly funding rate into a simple annualized percentage.

    Hyperliquid pays funding every hour, so a rate of 0.00125%/hour is
    0.00125% * 24 * 365 ~= 10.95%/year. Simple (not compounded) annualization
    is the market convention for quoting funding.
    """
    return hourly_rate * 24 * 365


def realized_vol_annualized(closes: Sequence[float], bars_per_year: float) -> float:
    """Annualized realized volatility from close-to-close log returns.

    E.g. for daily candles pass bars_per_year=365. BTC historically runs
    ~40-60% annualized; a memecoin can run 150%+. Vol is the denominator of
    every sizing decision in this project.
    """
    if len(closes) < 3:
        raise ValueError("need at least 3 closes")
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(bars_per_year)
