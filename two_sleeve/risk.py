"""Position sizing and the rules that keep sleeve 2 from eating sleeve 1.

The most important code in the repo. Strategy signals decide *when* to trade;
this module decides *how much*, and its answer is usually "less than you'd
like". A tiny account survives on discipline, not on picking winners.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizedTrade:
    """A trade the risk engine is willing to let through."""

    symbol: str
    side: str                 # "long" or "short"
    notional_usd: float       # position size in USD at entry
    entry: float
    stop: float
    risk_usd: float           # what we lose if the stop is hit (ex-fees)
    leverage: float           # notional / margin posted
    reason: str


def fixed_fractional_size(
    equity_usd: float,
    risk_fraction: float,
    entry: float,
    stop: float,
    max_leverage: float,
    min_notional_usd: float,
) -> float:
    """Return the position notional (USD) that risks `risk_fraction` of equity
    if the stop is hit. Returns 0.0 if the trade can't be sized legally.

    The core identity:  risk_usd = notional * |entry - stop| / entry
    so:                 notional = risk_usd * entry / |entry - stop|

    Then two caps:
      * leverage cap — margin posted is notional/leverage; we never let
        notional exceed equity * max_leverage.
      * exchange minimum — if risking the right amount would require a
        position below the exchange minimum order, the correct trade size is
        ZERO, not the minimum. Trading bigger than your risk budget because
        the exchange forces you to is how small accounts die.
    """
    if equity_usd <= 0 or entry <= 0:
        return 0.0
    stop_distance = abs(entry - stop)
    if stop_distance == 0:
        return 0.0
    risk_usd = equity_usd * risk_fraction
    notional = risk_usd * entry / stop_distance
    notional = min(notional, equity_usd * max_leverage)
    if notional < min_notional_usd:
        return 0.0
    return notional


def size_trade(
    symbol: str,
    side: str,
    equity_usd: float,
    risk_fraction: float,
    entry: float,
    stop: float,
    max_leverage: float,
    min_notional_usd: float,
    reason: str = "",
) -> SizedTrade | None:
    """Fully validate + size a proposed trade. None means 'do not trade'."""
    if side not in ("long", "short"):
        raise ValueError(f"side must be 'long' or 'short', got {side!r}")
    if side == "long" and stop >= entry:
        return None  # a long's stop must be below entry
    if side == "short" and stop <= entry:
        return None  # a short's stop must be above entry
    notional = fixed_fractional_size(
        equity_usd, risk_fraction, entry, stop, max_leverage, min_notional_usd
    )
    if notional <= 0:
        return None
    risk_usd = notional * abs(entry - stop) / entry
    return SizedTrade(
        symbol=symbol,
        side=side,
        notional_usd=round(notional, 2),
        entry=entry,
        stop=stop,
        risk_usd=round(risk_usd, 2),
        leverage=round(notional / equity_usd, 2),
        reason=reason,
    )


@dataclass(frozen=True)
class KillSwitch:
    """Monthly circuit breaker for the venture sleeve.

    The venture sleeve is *allowed* to lose its whole monthly budget — but it
    must do so in several small trades, not one big one, because the goal is
    reps and lessons. Once the month's loss budget is spent, the sleeve stops
    opening trades until the next deposit.
    """

    month_start_equity_usd: float
    max_monthly_loss_fraction: float = 1.0   # venture sleeve may go to zero
    max_open_trades: int = 2

    def halted(self, current_equity_usd: float) -> bool:
        loss = self.month_start_equity_usd - current_equity_usd
        budget = self.month_start_equity_usd * self.max_monthly_loss_fraction
        return loss >= budget

    def can_open(self, current_equity_usd: float, open_trades: int) -> bool:
        return not self.halted(current_equity_usd) and open_trades < self.max_open_trades


def carry_liquidation_buffer(
    entry_price: float,
    leverage: float,
    maintenance_margin_fraction: float,
) -> float:
    """For the SHORT PERP leg of the carry trade: the estimated liquidation
    PRICE — the absolute level price must rise to before liquidation.

    Approximation for an isolated short: with initial margin 1/leverage and
    maintenance margin m, liquidation is near price * (1 + 1/L - m).
    At 2x with m=0.5% (0.005) that's about +49.5% — price must rise ~49.5%
    against the short before the carry position is in real trouble. This is
    why the carry sleeve caps perp leverage at 2x: BTC has done +50% in a
    month exactly once in a decade; a 1x-2x short with weekly rebalancing
    survives everything short of that.

    NOTE: the spot leg gains what the short leg loses — the *position* is
    hedged. Liquidation risk is purely about margin mechanics on the perp
    account, which is why we hold margin headroom there.
    """
    if leverage <= 0:
        raise ValueError("leverage must be positive")
    return entry_price * (1.0 + 1.0 / leverage - maintenance_margin_fraction)
