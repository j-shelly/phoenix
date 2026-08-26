"""YOLO mode — house-money entertainment trades, deliberately OUTSIDE the
two-sleeve system.

Context that makes this sane: the Phoenix test program hands out a fixed
budget of non-withdrawable credits each month. Profits are not retained; the
only thing you keep is what you learn. Under those rules, high-leverage
trades that sometimes END IN LIQUIDATION are not a failure of discipline —
they are the point. Watching a position go +30% and then evaporate teaches
margin mechanics, funding, and slippage in a way the careful sleeves never
will, and it costs the house, not you.

Rules that survive even here (the non-negotiables):
  * this module PRINTS ideas; it never trades — same advisor rule as the rest;
  * ISOLATED margin only: one liquidation eats one stake, never the account.
    (Also the better lesson plan — $100 buys several liquidations, not one.)
  * the disciplined venture engine, its kill switch, and its stats are
    untouched — YOLO trades journal under sleeve "yolo", never "venture";
  * stakes below the exchange minimum are refused, not sized up.

Signal menu — one idea each per run, when the market offers one. These scan
EVERY liquid perp, not just the majors, because the fun lives in the tails:
  moonshot     — chase the day's biggest pump. Sometimes the train keeps
                 going; usually you're the exit liquidity. Feel both.
  knife_catch  — buy the day's biggest dump. Worse odds than a coin flip,
                 which is exactly why it pays when it works.
  squeeze      — fade the most extreme funding rate: stand in front of the
                 crowd and collect funding while you wait to be run over.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .hyperliquid import HyperliquidPublic, PerpSnapshot


@dataclass(frozen=True)
class YoloIdea:
    symbol: str
    flavor: str               # "moonshot" | "knife_catch" | "squeeze"
    side: str                 # "long" | "short"
    margin_usd: float         # the stake — the most this idea can lose
    notional_usd: float       # margin * leverage
    leverage: float
    entry: float
    est_liq_price: float
    liq_move: float           # fractional adverse move to liquidation (0.09 = 9%)
    why: str


def estimate_liquidation(entry: float, side: str, leverage: float,
                         market_max_leverage: int) -> tuple[float, float]:
    """(liquidation price, fractional adverse move) for an ISOLATED position.

    Hyperliquid convention: maintenance margin is half the initial margin at
    the market's max leverage, m = 1/(2*max_leverage). An isolated position
    at leverage L is liquidated roughly when price moves 1/L - m against it.
    At 10x on a 20x-max market that's 10% - 2.5% = 7.5%. Phoenix's exact
    maintenance schedule may differ — read the number in the app before
    clicking; the order of magnitude is what matters.
    """
    if leverage <= 0:
        raise ValueError("leverage must be positive")
    m = 1.0 / (2.0 * max(market_max_leverage, 1))
    move = max(1.0 / leverage - m, 0.0)
    price = entry * (1.0 - move) if side == "long" else entry * (1.0 + move)
    return price, move


def scan_yolo(client: HyperliquidPublic, cfg: Config,
              sleeve_equity_usd: float | None = None) -> list[YoloIdea]:
    """Scan every liquid perp for today's most entertaining trades.

    Snapshot-only on purpose: one API call, no history — YOLO ideas are about
    what the market is doing RIGHT NOW, and the whole mode is a toy.
    """
    ycfg = cfg.yolo
    equity = cfg.venture_equity if sleeve_equity_usd is None else sleeve_equity_usd
    margin_usd = equity * ycfg.stake_fraction
    snaps = [s for s in client.perp_snapshots()
             if s.day_volume_usd >= ycfg.min_day_volume_usd and s.mark_price > 0]
    ideas: list[YoloIdea] = []

    def build(snap: PerpSnapshot, flavor: str, side: str, why: str) -> None:
        leverage = min(ycfg.leverage, float(snap.max_leverage))
        notional = margin_usd * leverage
        # Refuse-below-minimum holds even in YOLO mode: a forced-bigger stake
        # is the one way this game could stop being free.
        if margin_usd <= 0 or notional < cfg.min_notional_usd:
            return
        liq_price, liq_move = estimate_liquidation(
            snap.mark_price, side, leverage, snap.max_leverage)
        ideas.append(YoloIdea(
            symbol=snap.coin, flavor=flavor, side=side,
            margin_usd=round(margin_usd, 2), notional_usd=round(notional, 2),
            leverage=leverage, entry=snap.mark_price,
            est_liq_price=liq_price, liq_move=liq_move, why=why))

    pump = max(snaps, key=lambda s: s.day_change, default=None)
    if pump is not None and pump.day_change >= ycfg.min_day_move:
        build(pump, "moonshot", "long",
              f"+{pump.day_change:.0%} in 24h on ${pump.day_volume_usd / 1e6:.0f}M "
              "volume — today's fastest train. Chasing it is usually buying "
              "someone's exit; occasionally it's day 1 of a 5x.")

    dump = min(snaps, key=lambda s: s.day_change, default=None)
    if dump is not None and dump.day_change <= -ycfg.min_day_move:
        build(dump, "knife_catch", "long",
              f"{dump.day_change:.0%} in 24h — today's sharpest knife. Dead-cat "
              "bounces are real and violent; so is the second leg down.")

    crowded = max(snaps, key=lambda s: abs(s.funding_apr), default=None)
    if crowded is not None and abs(crowded.funding_apr) >= ycfg.min_abs_funding_apr:
        side = "short" if crowded.funding_apr > 0 else "long"
        crowd = "longs" if side == "short" else "shorts"
        build(crowded, "squeeze", side,
              f"funding {crowded.funding_apr:+.0%} APR — {crowd} are crowded and "
              f"paying through the nose. You collect funding standing in front "
              "of them; the squeeze pays you or flattens you.")

    return ideas
