from pathlib import Path

from two_sleeve.ledger import Ledger, TradeClose, TradeOpen


def make_ledger(tmp_path: Path) -> Ledger:
    return Ledger(path=tmp_path / "ledger.jsonl")


def test_roundtrip_open_close(tmp_path):
    led = make_ledger(tmp_path)
    t = TradeOpen(sleeve="venture", symbol="SOL", side="long",
                  notional_usd=30, entry=150.0, stop=142.0,
                  thesis="20-day breakout with rising volume")
    led.append(t)
    assert len(led.open_trades()) == 1

    led.append(TradeClose(ref=t.id, exit=160.0, pnl_usd=2.0, fees_usd=0.05,
                          lesson="trailed too tight, gave back half the move"))
    assert led.open_trades() == []
    assert len(led.closed_trades()) == 1


def test_summary_math(tmp_path):
    led = make_ledger(tmp_path)
    a = TradeOpen(sleeve="venture", symbol="A", side="long", notional_usd=10,
                  entry=1.0, stop=0.9, thesis="t")
    b = TradeOpen(sleeve="venture", symbol="B", side="long", notional_usd=10,
                  entry=1.0, stop=0.9, thesis="t")
    led.append(a)
    led.append(b)
    led.append(TradeClose(ref=a.id, exit=1.2, pnl_usd=2.0, fees_usd=0.5, lesson="l"))
    led.append(TradeClose(ref=b.id, exit=0.9, pnl_usd=-1.0, fees_usd=0.5, lesson="l"))
    s = led.summary("venture")
    assert s["trades"] == 2
    assert s["net_pnl_usd"] == 0.0     # (2.0-0.5) + (-1.0-0.5)
    assert s["win_rate"] == 0.5


def test_summary_filters_by_sleeve(tmp_path):
    led = make_ledger(tmp_path)
    c = TradeOpen(sleeve="carry", symbol="BTC", side="carry", notional_usd=60,
                  entry=1.0, stop=None, thesis="funding harvest")
    led.append(c)
    led.append(TradeClose(ref=c.id, exit=1.0, pnl_usd=0.4, fees_usd=0.1, lesson="l"))
    assert led.summary("venture")["trades"] == 0
    assert led.summary("carry")["trades"] == 1
    assert led.summary()["trades"] == 1


def test_missing_file_is_empty(tmp_path):
    led = make_ledger(tmp_path)
    assert led.records() == []
    assert led.summary() == {
        "trades": 0, "net_pnl_usd": 0, "win_rate": None,
        "avg_win_usd": None, "avg_loss_usd": None, "open_trades": 0,
    }
