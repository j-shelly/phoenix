import math

import pytest

from two_sleeve.indicators import (
    annualize_hourly_funding,
    atr,
    donchian,
    ema,
    realized_vol_annualized,
    rsi,
    sma,
    true_range,
    zscore,
)


def test_sma_basic():
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert sma([1, 2, 3, 4], 4) == 2.5


def test_sma_rejects_short_series():
    with pytest.raises(ValueError):
        sma([1, 2], 3)


def test_ema_constant_series_is_constant():
    assert ema([5.0] * 30, 10) == pytest.approx(5.0)


def test_ema_tracks_recent_values_more_than_sma():
    series = [10.0] * 20 + [20.0] * 5
    assert ema(series, 10) > sma(series, 10)  # EMA reacts faster to the jump


def test_donchian():
    highs = [5, 7, 6, 9, 8]
    lows = [1, 3, 2, 4, 5]
    assert donchian(highs, lows, 3) == (9, 2)
    assert donchian(highs, lows, 5) == (9, 1)


def test_true_range_covers_gaps():
    # Bar span is 2, but price gapped down from prev close 20 -> TR is 10.
    assert true_range(high=12, low=10, prev_close=20) == 10


def test_atr_on_steady_bars():
    n = 20
    highs = [102.0] * n
    lows = [98.0] * n
    closes = [100.0] * n
    assert atr(highs, lows, closes, period=14) == pytest.approx(4.0)


def test_rsi_all_gains_is_100():
    closes = list(range(1, 20))
    assert rsi([float(c) for c in closes], 14) == 100.0


def test_rsi_symmetric_chop_is_50():
    closes = [100.0, 101.0] * 15
    assert rsi(closes, 14) == pytest.approx(50.0, abs=5.0)


def test_zscore():
    values = [0.0] * 29 + [10.0]
    z = zscore(values, 30)
    assert z > 5.0  # a huge outlier vs. a flat series


def test_zscore_flat_series_is_zero():
    assert zscore([1.0] * 10, 10) == 0.0


def test_annualize_hourly_funding():
    # 0.00125%/hour (0.0000125) -> ~10.95%/year, HL's "default" funding level
    assert annualize_hourly_funding(0.0000125) == pytest.approx(0.1095)


def test_realized_vol_positive():
    closes = [100 * math.exp(0.01 * ((-1) ** i)) for i in range(50)]
    v = realized_vol_annualized(closes, bars_per_year=365)
    assert v > 0
