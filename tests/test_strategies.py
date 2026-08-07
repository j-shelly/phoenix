"""Strategy-engine tests against a canned fake exchange — no network."""

import math

import pytest

from two_sleeve.carry import build_plan, evaluate_candidates
from two_sleeve.config import Config
from two_sleeve.hyperliquid import PerpSnapshot
from two_sleeve.venture import scan_breakouts


def snap(coin, price, funding_hourly, oi=50e6, vol=100e6):
    return PerpSnapshot(coin=coin, mark_price=price, mid_price=price,
                        oracle_price=price, funding_hourly=funding_hourly,
                        premium=0.0001, open_interest_usd=oi,
                        day_volume_usd=vol, max_leverage=40,
                        prev_day_price=price * 0.99)


class FakeClient:
    """Stands in for HyperliquidPublic with fully scripted data."""

    def __init__(self, snapshots, funding=None, candles=None):
        self._snapshots = snapshots
        self._funding = funding or {}
        self._candles = candles or {}

    def perp_snapshots(self):
        return self._snapshots

    def funding_aprs_realized(self, coin, days=30):
        if coin not in self._funding:
            raise ConnectionError("no data")
        return self._funding[coin]

    def daily_bars(self, coin, days):
        if coin not in self._candles:
            raise ConnectionError("no data")
        return self._candles[coin]


GOOD_FUNDING = {"mean_apr": 0.12, "min_apr": -0.05, "max_apr": 0.60,
                "pct_hours_negative": 0.10, "hours": 720}
BAD_FUNDING = {"mean_apr": 0.01, "min_apr": -0.30, "max_apr": 0.20,
               "pct_hours_negative": 0.55, "hours": 720}


def test_carry_picks_best_qualified_coin():
    cfg = Config(total_equity_usd=200)
    client = FakeClient(
        [snap("BTC", 100_000, 0.0000125), snap("ETH", 5_000, 0.00002),
         snap("SOL", 200, 0.00001), snap("HYPE", 40, 0.00001)],
        funding={"BTC": GOOD_FUNDING,
                 "ETH": dict(GOOD_FUNDING, mean_apr=0.18),
                 "SOL": BAD_FUNDING,
                 "HYPE": GOOD_FUNDING},
    )
    cands = evaluate_candidates(client, cfg)
    assert cands[0].coin == "ETH"            # highest net APR wins
    sol = next(c for c in cands if c.coin == "SOL")
    assert sol.disqualified is not None      # unreliable funding rejected

    plan = build_plan(cands, cfg)
    assert plan.action == "enter"
    assert plan.coin == "ETH"
    # Legs must match (delta-neutral) and sum to the sleeve.
    assert plan.spot_notional_usd == plan.perp_short_notional_usd
    assert plan.spot_notional_usd + plan.perp_margin_usd == pytest.approx(
        cfg.carry_equity)
    assert plan.perp_leverage < 1.0          # sub-1x short by construction
    assert plan.est_liquidation_price > 5_000 * 1.5


def test_carry_accumulates_when_sleeve_too_small():
    cfg = Config(total_equity_usd=50)        # carry sleeve = $40 < $60 floor
    client = FakeClient([snap("BTC", 100_000, 0.0000125)],
                        funding={"BTC": GOOD_FUNDING})
    plan = build_plan(evaluate_candidates(client, cfg), cfg)
    assert plan.action == "accumulate"
    assert plan.perp_short_notional_usd == 0.0


def test_carry_holds_usdc_when_nothing_qualifies():
    cfg = Config(total_equity_usd=500)
    client = FakeClient([snap("BTC", 100_000, 0.0)],
                        funding={"BTC": BAD_FUNDING})
    plan = build_plan(evaluate_candidates(client, cfg), cfg)
    assert plan.action == "hold_usdc"


def test_carry_fee_drag_reduces_net_apr():
    cfg = Config(total_equity_usd=200)
    client = FakeClient([snap("BTC", 100_000, 0.0000125)],
                        funding={"BTC": GOOD_FUNDING})
    c = evaluate_candidates(client, cfg)[0]
    assert c.net_apr < c.expected_apr
    drag = c.expected_apr - c.net_apr
    expected_drag = cfg.fees.carry_round_trip * 365 / cfg.carry.expected_hold_days
    assert drag == pytest.approx(expected_drag)


def _trend_candles(n=90, start=100.0, breakout_bump=0.0, breakout_volume=2.0):
    """Synthetic up-trending daily bars WITH down days (a monotonic series
    pins RSI at 100 and the entry filter rightly refuses it); final bar
    optionally breaks out on elevated volume."""
    closes, highs, lows = [], [], []
    px = start
    for i in range(n):
        px *= 1 + 0.012 * math.sin(i / 3.0) + 0.003
        closes.append(px)
        highs.append(px * 1.01)
        lows.append(px * 0.99)
    # A few red days before the last bar keep RSI honest (real breakouts
    # come out of pullbacks, and monotonic series pin RSI at ~100).
    for j in range(n - 4, n - 1):
        closes[j] = closes[j - 1] * 0.985
        highs[j] = closes[j] * 1.01
        lows[j] = closes[j] * 0.98
    volumes = [1000.0] * n
    if breakout_bump:
        closes[-1] = max(highs[:-1][-25:]) * (1 + breakout_bump)
        highs[-1] = closes[-1] * 1.005
        volumes[-1] = 1000.0 * breakout_volume
    return highs, lows, closes, volumes


def test_breakout_long_detected_and_sized():
    cfg = Config(total_equity_usd=500)       # venture sleeve = $100
    candles = _trend_candles(breakout_bump=0.02)
    last = candles[2][-1]
    client = FakeClient([snap("BTC", last, 0.0000125)],
                        candles={"BTC": candles})
    ideas = scan_breakouts(client, cfg)
    assert len(ideas) == 1
    idea = ideas[0]
    assert idea.signal == "breakout_long"
    t = idea.trade
    assert t.stop < t.entry
    # Risk never exceeds the per-trade budget; the leverage cap may shrink it
    # further (tight stop -> big implied notional -> cap binds -> less risk).
    assert t.risk_usd <= cfg.venture_equity * cfg.venture.risk_per_trade + 0.01
    assert t.risk_usd > 0
    assert t.notional_usd <= cfg.venture_equity * cfg.venture.max_leverage + 0.01


def test_no_breakout_no_idea():
    cfg = Config(total_equity_usd=500)
    candles = _trend_candles(breakout_bump=0.0)
    client = FakeClient([snap("BTC", candles[2][-1], 0.0000125)],
                        candles={"BTC": candles})
    # A trend without a FRESH channel break may or may not trigger depending
    # on the last bar; force the last close inside the prior channel.
    highs, lows, closes, _volumes = candles
    closes[-1] = closes[-10]
    highs[-1] = closes[-1] * 1.005
    lows[-1] = closes[-1] * 0.995
    assert scan_breakouts(client, cfg) == []


def test_low_volume_breakout_rejected():
    cfg = Config(total_equity_usd=500)
    candles = _trend_candles(breakout_bump=0.02, breakout_volume=0.5)
    client = FakeClient([snap("BTC", candles[2][-1], 0.0000125)],
                        candles={"BTC": candles})
    assert scan_breakouts(client, cfg) == []


def test_illiquid_coin_skipped():
    cfg = Config(total_equity_usd=500)
    candles = _trend_candles(breakout_bump=0.02)
    client = FakeClient([snap("BTC", candles[2][-1], 0.0000125, vol=1e6)],
                        candles={"BTC": candles})
    assert scan_breakouts(client, cfg) == []


def test_tiny_sleeve_refuses_trade_below_minimum():
    # $10 venture sleeve -> 30% risk = $3; with a ~6% stop the notional would
    # be ~$50... which is fine; instead make equity so small notional < $10.
    cfg = Config(total_equity_usd=10)        # venture sleeve = $2
    candles = _trend_candles(breakout_bump=0.02)
    client = FakeClient([snap("BTC", candles[2][-1], 0.0000125)],
                        candles={"BTC": candles})
    ideas = scan_breakouts(client, cfg)
    for idea in ideas:
        assert idea.trade.notional_usd >= cfg.min_notional_usd
