"""Sleeve 2 — the venture (high-risk, learning) engine.

Ground rules this engine enforces so the fun stays fun:
  * risk per trade is a fixed fraction of the SLEEVE — several small deaths
    a month, never one big one;
  * at most 2 concurrent trades; leverage capped at 3x (above that, fees and
    liquidation mechanics are the counterparty, not the market);
  * every idea comes with entry, stop, and a written thesis — if you can't
    say why, you don't get a size.

Signals, in order of trustworthiness:
  1. Donchian breakout (trend): close breaks the prior 20-day high with the
     50-day trend up. The oldest idea in systematic trading; win rate ~35-45%
     but winners run. The trailing ATR stop is what makes it survivable.
  2. Breakdown short: the mirror image, for down-trends.
  3. Funding-extreme fade (OFF by default): when funding is wildly positive,
     longs are crowded and paying through the nose; the squeeze usually comes.
     Contrarian, harder to time — enable in config only after you've watched
     it signal for a month.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .config import Config
from .hyperliquid import HyperliquidPublic
from .indicators import atr, donchian, ema, rsi, sma, zscore
from .risk import SizedTrade, size_trade

# Liquid, established perps we scan for breakouts. Deliberately short list:
# sleeve 2 teaches process, and majors have the cleanest data and spreads.
SCAN_UNIVERSE = ("BTC", "ETH", "SOL", "HYPE", "DOGE", "XRP")

# Daily bars needed: 50d EMA + buffer for ATR/RSI seeding.
LOOKBACK_DAYS = 80


@dataclass(frozen=True)
class VentureIdea:
    symbol: str
    signal: str            # "breakout_long" | "breakdown_short" | "fade_short" | "fade_long"
    trade: SizedTrade
    trigger_detail: str


def scan_breakouts(client: HyperliquidPublic, cfg: Config,
                   sleeve_equity_usd: float | None = None) -> list[VentureIdea]:
    """Scan the universe for fresh Donchian breakouts/breakdowns, fully sized.

    "Fresh" = the LATEST daily close crossed the prior N-day extreme. A
    breakout from three days ago is not a signal, it's a chase.
    """
    vcfg = cfg.venture
    equity = cfg.venture_equity if sleeve_equity_usd is None else sleeve_equity_usd
    snapshots = {s.coin: s for s in client.perp_snapshots()}
    ideas: list[VentureIdea] = []

    for coin in SCAN_UNIVERSE:
        snap = snapshots.get(coin)
        if snap is None or snap.day_volume_usd < vcfg.min_day_volume_usd:
            continue
        try:
            highs, lows, closes, volumes = client.daily_bars(coin, LOOKBACK_DAYS)
        except ConnectionError:
            continue
        if len(closes) < vcfg.trend_ema_days + 2:
            continue

        last_close = closes[-1]
        # Channel from bars BEFORE the latest completed bar — that bar must
        # break the channel of the days preceding it. (daily_bars already
        # dropped the still-forming current-day candle.)
        chan_high, chan_low = donchian(highs[:-1], lows[:-1], vcfg.breakout_days)
        trend = ema(closes, vcfg.trend_ema_days)
        bar_atr = atr(highs, lows, closes, vcfg.atr_days)
        momentum = rsi(closes, 14)
        # Volume confirmation: low-volume breakouts fail disproportionately.
        vol_avg = sma(volumes[:-1], vcfg.volume_confirm_bars)
        volume_ok = vol_avg == 0 or volumes[-1] > vol_avg

        if (last_close > chan_high and last_close > trend
                and momentum < vcfg.rsi_max_for_entry and volume_ok):
            stop = last_close - vcfg.stop_atr_mult * bar_atr
            trade = size_trade(coin, "long", equity, vcfg.risk_per_trade,
                               entry=last_close, stop=stop,
                               max_leverage=vcfg.max_leverage,
                               min_notional_usd=cfg.min_notional_usd,
                               reason=f"{vcfg.breakout_days}d breakout, above {vcfg.trend_ema_days}d EMA")
            if trade:
                ideas.append(VentureIdea(
                    symbol=coin, signal="breakout_long", trade=trade,
                    trigger_detail=(f"close {last_close:g} > {vcfg.breakout_days}d high "
                                    f"{chan_high:g}; EMA{vcfg.trend_ema_days} {trend:.4g}; "
                                    f"RSI {momentum:.0f}; ATR {bar_atr:.4g}"),
                ))
        elif last_close < chan_low and last_close < trend and volume_ok:
            stop = last_close + vcfg.stop_atr_mult * bar_atr
            trade = size_trade(coin, "short", equity, vcfg.risk_per_trade,
                               entry=last_close, stop=stop,
                               max_leverage=vcfg.max_leverage,
                               min_notional_usd=cfg.min_notional_usd,
                               reason=f"{vcfg.breakout_days}d breakdown, below {vcfg.trend_ema_days}d EMA")
            if trade:
                ideas.append(VentureIdea(
                    symbol=coin, signal="breakdown_short", trade=trade,
                    trigger_detail=(f"close {last_close:g} < {vcfg.breakout_days}d low "
                                    f"{chan_low:g}; EMA{vcfg.trend_ema_days} {trend:.4g}; "
                                    f"ATR {bar_atr:.4g}"),
                ))
    return ideas


def scan_funding_fades(client: HyperliquidPublic, cfg: Config,
                       sleeve_equity_usd: float | None = None) -> list[VentureIdea]:
    """Contrarian funding-extreme signals. Disabled unless cfg.venture.fade_enabled.

    Logic: pull 30 days of hourly funding; if the current rate is both extreme
    in level (|APR| above threshold) AND extreme vs. its own recent history
    (z-score), the crowd is offsides. Fade small, stop 2.5 ATR away.
    """
    vcfg = cfg.venture
    if not vcfg.fade_enabled:
        return []
    equity = cfg.venture_equity if sleeve_equity_usd is None else sleeve_equity_usd
    ideas: list[VentureIdea] = []

    for coin in SCAN_UNIVERSE:
        try:
            now_ms = int(time.time() * 1000)
            hist = client.funding_history(coin, now_ms - 30 * 86400_000, now_ms)
            highs, lows, closes, _volumes = client.daily_bars(coin, 30)
        except ConnectionError:
            continue
        rates = [float(h["fundingRate"]) for h in hist]
        if len(rates) < 100 or len(closes) < 16:
            continue
        apr = rates[-1] * 24 * 365
        z = zscore(rates, min(len(rates), 30 * 24))
        bar_atr = atr(highs, lows, closes, 14)
        last_close = closes[-1]

        side = None
        if apr > vcfg.fade_funding_apr and z > vcfg.fade_zscore:
            side = "short"   # longs crowded and paying — fade them
            stop = last_close + 2.5 * bar_atr
        elif apr < -vcfg.fade_funding_apr and z < -vcfg.fade_zscore:
            side = "long"    # shorts crowded and paying — fade them
            stop = last_close - 2.5 * bar_atr
        if side is None:
            continue
        trade = size_trade(coin, side, equity, vcfg.risk_per_trade,
                           entry=last_close, stop=stop,
                           max_leverage=vcfg.max_leverage,
                           min_notional_usd=cfg.min_notional_usd,
                           reason=f"funding fade: APR {apr:.0%}, z {z:.1f}")
        if trade:
            ideas.append(VentureIdea(
                symbol=coin, signal=f"fade_{side}", trade=trade,
                trigger_detail=f"funding APR {apr:.0%} at z={z:.1f} — crowd offsides",
            ))
    return ideas
