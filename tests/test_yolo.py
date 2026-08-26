"""YOLO-mode tests against canned snapshots — no network.

YOLO mode is outside the two-sleeve risk framework ON PURPOSE, but the rules
it does keep (isolated-stake sizing, market leverage caps, refuse-below-
minimum, liquid markets only) are pinned here so they can't rot silently.
"""

import pytest

from two_sleeve.config import Config
from two_sleeve.hyperliquid import PerpSnapshot
from two_sleeve.yolo import estimate_liquidation, scan_yolo


def snap(coin, price, *, change=0.0, funding_hourly=0.0, vol=100e6, max_lev=20):
    return PerpSnapshot(coin=coin, mark_price=price, mid_price=price,
                        oracle_price=price, funding_hourly=funding_hourly,
                        premium=0.0, open_interest_usd=50e6,
                        day_volume_usd=vol, max_leverage=max_lev,
                        prev_day_price=price / (1 + change))


class FakeClient:
    def __init__(self, snapshots):
        self._snapshots = snapshots

    def perp_snapshots(self):
        return self._snapshots


QUIET = [snap("BTC", 100_000, change=0.02, funding_hourly=0.00001),
         snap("ETH", 5_000, change=-0.03)]


def test_moonshot_chases_biggest_pump():
    cfg = Config(total_equity_usd=100)       # venture $20 -> $10 stake
    client = FakeClient(QUIET + [snap("WIF", 2.0, change=0.40),
                                 snap("PEPE", 1.0, change=0.15)])
    ideas = scan_yolo(client, cfg)
    moon = [i for i in ideas if i.flavor == "moonshot"]
    assert len(moon) == 1
    idea = moon[0]
    assert (idea.symbol, idea.side) == ("WIF", "long")   # biggest pump wins
    assert idea.margin_usd == pytest.approx(20 * cfg.yolo.stake_fraction)
    assert idea.notional_usd == pytest.approx(idea.margin_usd * idea.leverage)
    assert idea.est_liq_price < idea.entry               # long liquidates below


def test_knife_catch_buys_biggest_dump():
    cfg = Config(total_equity_usd=100)
    client = FakeClient(QUIET + [snap("DOGE", 0.08, change=-0.35)])
    knives = [i for i in scan_yolo(client, cfg) if i.flavor == "knife_catch"]
    assert len(knives) == 1
    assert (knives[0].symbol, knives[0].side) == ("DOGE", "long")


def test_squeeze_fades_the_paying_crowd():
    cfg = Config(total_equity_usd=100)
    # +0.0001/hr = +87.6% APR: longs crowded -> short; mirror for negative.
    client = FakeClient(QUIET + [snap("HYPE", 80.0, funding_hourly=0.0001)])
    squeezes = [i for i in scan_yolo(client, cfg) if i.flavor == "squeeze"]
    assert [(i.symbol, i.side) for i in squeezes] == [("HYPE", "short")]
    assert squeezes[0].est_liq_price > squeezes[0].entry  # short liquidates above

    client = FakeClient(QUIET + [snap("HYPE", 80.0, funding_hourly=-0.0001)])
    squeezes = [i for i in scan_yolo(client, cfg) if i.flavor == "squeeze"]
    assert [(i.symbol, i.side) for i in squeezes] == [("HYPE", "long")]


def test_quiet_market_offers_nothing():
    assert scan_yolo(FakeClient(QUIET), Config(total_equity_usd=100)) == []


def test_thin_market_skipped_even_when_pumping():
    cfg = Config(total_equity_usd=100)
    client = FakeClient(QUIET + [snap("RUG", 0.01, change=0.90, vol=1e6)])
    assert scan_yolo(client, cfg) == []


def test_leverage_capped_by_market_max():
    cfg = Config(total_equity_usd=100)       # yolo.leverage = 10
    client = FakeClient(QUIET + [snap("WIF", 2.0, change=0.40, max_lev=5)])
    idea = scan_yolo(client, cfg)[0]
    assert idea.leverage == 5.0
    # liq move = 1/L - 1/(2*max_lev) = 0.2 - 0.1
    assert idea.liq_move == pytest.approx(0.10)


def test_refuses_stake_below_exchange_minimum():
    cfg = Config(total_equity_usd=1)         # $0.10 stake * 10x = $1 < $10 min
    client = FakeClient(QUIET + [snap("WIF", 2.0, change=0.40)])
    assert scan_yolo(client, cfg) == []


def test_estimate_liquidation_math():
    # 10x long on a 20x-max market: move = 1/10 - 1/40 = 7.5%
    price, move = estimate_liquidation(100.0, "long", 10.0, 20)
    assert move == pytest.approx(0.075)
    assert price == pytest.approx(92.5)
    price, move = estimate_liquidation(100.0, "short", 10.0, 20)
    assert price == pytest.approx(107.5)
