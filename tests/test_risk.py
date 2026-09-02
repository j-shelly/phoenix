import pytest

from two_sleeve.risk import (
    KillSwitch,
    carry_liquidation_buffer,
    fixed_fractional_size,
    size_trade,
)


def test_fixed_fractional_basic():
    # $1000 equity, risk 1% = $10. Entry 100, stop 95 -> 5% stop distance.
    # notional = 10 * 100 / 5 = $200.
    n = fixed_fractional_size(1000, 0.01, entry=100, stop=95,
                              max_leverage=3, min_notional_usd=10)
    assert n == pytest.approx(200.0)


def test_leverage_cap_binds():
    # Tight stop would imply huge notional; cap at 3x equity.
    n = fixed_fractional_size(100, 0.05, entry=100, stop=99.9,
                              max_leverage=3, min_notional_usd=10)
    assert n == pytest.approx(300.0)


def test_below_exchange_minimum_means_zero_not_minimum():
    # Correct sizing would be $4 notional; min order is $10 -> refuse.
    n = fixed_fractional_size(20, 0.01, entry=100, stop=95,
                              max_leverage=3, min_notional_usd=10)
    assert n == 0.0


def test_zero_stop_distance_refused():
    assert fixed_fractional_size(100, 0.01, 100, 100, 3, 10) == 0.0


def test_size_trade_rejects_stop_on_wrong_side():
    assert size_trade("BTC", "long", 100, 0.02, entry=100, stop=105,
                      max_leverage=3, min_notional_usd=10) is None
    assert size_trade("BTC", "short", 100, 0.02, entry=100, stop=95,
                      max_leverage=3, min_notional_usd=10) is None


def test_size_trade_risk_matches_request():
    t = size_trade("ETH", "long", 500, 0.02, entry=2000, stop=1900,
                   max_leverage=3, min_notional_usd=10)
    assert t is not None
    assert t.risk_usd == pytest.approx(500 * 0.02, abs=0.01)


def test_kill_switch_halts_after_budget_spent():
    ks = KillSwitch(month_start_equity_usd=20.0, max_monthly_loss_fraction=1.0)
    assert not ks.halted(current_equity_usd=5.0)
    assert ks.halted(current_equity_usd=0.0)
    assert ks.can_open(current_equity_usd=10.0, open_trades=1)
    assert not ks.can_open(current_equity_usd=10.0, open_trades=2)


def test_carry_liquidation_buffer_2x():
    liq = carry_liquidation_buffer(entry_price=100.0, leverage=2.0,
                                   maintenance_margin_fraction=0.005)
    # ~ +49.5% above entry
    assert liq == pytest.approx(149.5)
