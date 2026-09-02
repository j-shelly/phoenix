"""Tests pinning the fixes from the adversarial review pass."""

import argparse
import json

import pytest

from two_sleeve.config import Config, _apply_overrides
from two_sleeve.hyperliquid import HyperliquidPublic
from two_sleeve.ledger import Ledger, TradeClose, TradeOpen

from tests.test_strategies import GOOD_FUNDING, FakeClient, _trend_candles, snap


def test_funding_history_paginates_past_500(monkeypatch):
    """The API caps responses at 500 entries; 30 days needs 720."""
    client = HyperliquidPublic()
    calls = []

    def fake_post(body):
        calls.append(body)
        start = body["startTime"]
        # 720 hourly entries total, served in capped pages from `start`.
        all_times = [1_000_000 + i * 3_600_000 for i in range(720)]
        page = [{"coin": "BTC", "fundingRate": "0.0000125", "time": t}
                for t in all_times if t >= start][:500]
        return page

    monkeypatch.setattr(client, "_post", fake_post)
    hist = client.funding_history("BTC", 1_000_000)
    assert len(hist) == 720
    assert len(calls) == 2
    times = [h["time"] for h in hist]
    assert len(set(times)) == 720  # no duplicates at the page boundary


def test_daily_bars_drops_in_progress_candle(monkeypatch):
    client = HyperliquidPublic()
    day = 24 * 3600 * 1000
    now_ms = 1_700_000_000_000
    monkeypatch.setattr("two_sleeve.hyperliquid.time.time", lambda: now_ms / 1000)
    today_open = now_ms - (now_ms % day)

    def fake_candles(coin, interval, start_ms, end_ms):
        bars = []
        for i in range(5, 0, -1):  # 5 completed days
            t = today_open - i * day
            bars.append({"t": t, "o": "1", "h": "2", "l": "0.5", "c": "1.5", "v": "100"})
        # the still-forming candle: partial volume, live "close"
        bars.append({"t": today_open, "o": "1", "h": "9", "l": "0.5", "c": "9", "v": "3"})
        return bars

    monkeypatch.setattr(client, "candles", fake_candles)
    highs, lows, closes, volumes = client.daily_bars("BTC", 5)
    assert len(closes) == 5
    assert closes[-1] == 1.5          # yesterday's completed close, not the live 9
    assert volumes[-1] == 100.0       # full-day volume, not the partial 3


def test_config_override_of_property_gives_friendly_error():
    with pytest.raises(KeyError, match="unknown config key"):
        _apply_overrides(Config(), {"carry_equity": 42})
    with pytest.raises(KeyError, match="unknown config key"):
        _apply_overrides(Config().fees, {"carry_round_trip": 0.1})


def test_config_override_of_real_fields_works():
    cfg = Config()
    _apply_overrides(cfg, {"total_equity_usd": 250,
                           "carry": {"min_net_apr": 0.09}})
    assert cfg.total_equity_usd == 250
    assert cfg.carry.min_net_apr == 0.09


def test_ledger_survives_malformed_line(tmp_path, capsys):
    path = tmp_path / "ledger.jsonl"
    led = Ledger(path=path)
    t = TradeOpen(sleeve="venture", symbol="SOL", side="long",
                  notional_usd=30, entry=150.0, stop=142.0, thesis="t")
    led.append(t)
    with path.open("a") as f:
        f.write('{"record": "close", "ref": "TRUNCATED')  # crashed mid-write
    led.append(TradeClose(ref=t.id, exit=160.0, pnl_usd=2.0, fees_usd=0.0,
                          lesson="l"))
    assert len(led.closed_trades()) == 1  # good records still readable
    assert "malformed ledger line" in capsys.readouterr().err


def test_summary_separates_paper_and_real(tmp_path):
    led = Ledger(path=tmp_path / "ledger.jsonl")
    real = TradeOpen(sleeve="venture", symbol="A", side="long", notional_usd=10,
                     entry=1.0, stop=0.9, thesis="t", paper=False)
    paper = TradeOpen(sleeve="venture", symbol="B", side="long", notional_usd=10,
                      entry=1.0, stop=0.9, thesis="t", paper=True)
    led.append(real)
    led.append(paper)
    led.append(TradeClose(ref=real.id, exit=0.8, pnl_usd=-20.0, fees_usd=0.0, lesson="l"))
    led.append(TradeClose(ref=paper.id, exit=2.0, pnl_usd=50.0, fees_usd=0.0, lesson="l"))
    assert led.summary("venture", paper=False)["net_pnl_usd"] == -20.0
    assert led.summary("venture", paper=True)["net_pnl_usd"] == 50.0
    assert led.summary("venture")["net_pnl_usd"] == 30.0  # unfiltered blends


def test_plan_kill_switch_blocks_ideas_after_real_monthly_loss(monkeypatch, tmp_path, capsys):
    from two_sleeve import cli

    led = Ledger(path=tmp_path / "ledger.jsonl")
    real = TradeOpen(sleeve="venture", symbol="SOL", side="long", notional_usd=30,
                     entry=150.0, stop=140.0, thesis="t", paper=False)
    led.append(real)
    # Lose the whole $20 venture budget this month, real money.
    led.append(TradeClose(ref=real.id, exit=140.0, pnl_usd=-20.0, fees_usd=0.1,
                          lesson="sized too big"))

    candles = _trend_candles(breakout_bump=0.02)  # a signal WOULD fire
    client = FakeClient([snap("BTC", candles[2][-1], 0.0000125)],
                        funding={"BTC": GOOD_FUNDING},
                        candles={"BTC": candles})
    monkeypatch.setattr(cli, "Ledger", lambda: led)
    monkeypatch.setattr(cli, "_client", lambda: client)
    monkeypatch.setattr(cli, "load_config", lambda: Config(total_equity_usd=100))

    assert cli.cmd_plan(argparse.Namespace()) == 0
    out = capsys.readouterr().out
    assert "KILL SWITCH" in out
    assert "IDEA" not in out          # no sized trades offered while halted


def test_plan_sizes_against_depleted_sleeve(monkeypatch, tmp_path, capsys):
    from two_sleeve import cli

    led = Ledger(path=tmp_path / "ledger.jsonl")
    real = TradeOpen(sleeve="venture", symbol="SOL", side="long", notional_usd=30,
                     entry=150.0, stop=145.0, thesis="t", paper=False)
    led.append(real)
    led.append(TradeClose(ref=real.id, exit=145.0, pnl_usd=-10.0, fees_usd=0.0,
                          lesson="l"))  # half the $20 budget gone

    candles = _trend_candles(breakout_bump=0.02)
    client = FakeClient([snap("BTC", candles[2][-1], 0.0000125)],
                        funding={"BTC": GOOD_FUNDING},
                        candles={"BTC": candles})
    monkeypatch.setattr(cli, "Ledger", lambda: led)
    monkeypatch.setattr(cli, "_client", lambda: client)
    monkeypatch.setattr(cli, "load_config", lambda: Config(total_equity_usd=100))

    assert cli.cmd_plan(argparse.Namespace()) == 0
    out = capsys.readouterr().out
    assert "IDEA 1" in out
    # Sized off $10 remaining, not $20: leverage cap 3x -> notional <= $30.
    import re
    m = re.search(r"size \$(\d+\.\d+)", out)
    assert m and float(m.group(1)) <= 30.0 + 0.01
