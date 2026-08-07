"""Sleeve 1 — the carry (funding-harvest) engine.

The trade, in one paragraph: perpetual futures have no expiry, so exchanges
keep the perp price glued to spot with an hourly "funding" payment between
longs and shorts. In bull-leaning markets longs outnumber shorts, funding is
positive, and SHORTS GET PAID. If you short the perp and simultaneously hold
the same dollar amount of the actual asset (spot), price moves cancel out —
spot gains offset perp losses and vice versa — and you pocket the funding.
It's the crypto version of a covered interest trade: boring by construction,
which is exactly what sleeve 1 is for.

What kills the trade (and what this module checks):
  * funding flips negative and stays there  -> exit rule on trailing APR
  * fees eat the yield at small size        -> fee amortization in net APR
  * short leg gets liquidated in a melt-up  -> leverage cap + margin buffer
  * illiquid coin, wide spreads             -> OI / volume floors
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .hyperliquid import HyperliquidPublic, PerpSnapshot
from .risk import carry_liquidation_buffer

HL_MAINTENANCE_MARGIN_APPROX = 0.005  # varies by asset/tier; conservative-ish


@dataclass(frozen=True)
class CarryCandidate:
    coin: str
    mark_price: float
    current_apr: float          # instantaneous funding, annualized
    realized_apr_30d: float     # trailing realized funding, annualized
    expected_apr: float         # blended estimate BEFORE fees
    net_apr: float              # after amortized entry+exit fees
    pct_hours_negative: float   # how often funding paid the wrong way lately
    open_interest_usd: float
    day_volume_usd: float
    disqualified: str | None    # None = tradeable; else the reason we refuse


@dataclass(frozen=True)
class CarryPlan:
    """Concrete, do-this-in-the-UI instructions for the carry sleeve."""

    action: str                 # "enter" | "hold_usdc" | "accumulate"
    coin: str | None
    sleeve_equity_usd: float
    spot_notional_usd: float
    perp_short_notional_usd: float
    perp_margin_usd: float
    perp_leverage: float
    est_liquidation_price: float | None
    expected_net_apr: float
    expected_monthly_usd: float
    notes: list[str]


def evaluate_candidates(client: HyperliquidPublic, cfg: Config) -> list[CarryCandidate]:
    """Score every coin in the carry universe. Never raises on a single coin —
    a coin that can't be evaluated is disqualified, not fatal."""
    snapshots = {s.coin: s for s in client.perp_snapshots()}
    ccfg = cfg.carry
    out: list[CarryCandidate] = []
    for coin in ccfg.universe:
        snap = snapshots.get(coin)
        if snap is None:
            out.append(_disqualified(coin, "no perp market found"))
            continue
        try:
            realized = client.funding_aprs_realized(coin, days=ccfg.realized_days)
        except ConnectionError:
            out.append(_disqualified(coin, "funding history unavailable"))
            continue
        expected = (
            ccfg.realized_weight * realized["mean_apr"]
            + (1.0 - ccfg.realized_weight) * snap.funding_apr
        )
        # Amortize round-trip fees over the expected holding period.
        fee_apr_drag = cfg.fees.carry_round_trip * (365.0 / ccfg.expected_hold_days)
        net = expected - fee_apr_drag

        reason = None
        if snap.open_interest_usd < ccfg.min_open_interest_usd:
            reason = f"open interest ${snap.open_interest_usd/1e6:.1f}M below floor"
        elif snap.day_volume_usd < ccfg.min_day_volume_usd:
            reason = f"day volume ${snap.day_volume_usd/1e6:.1f}M below floor"
        elif realized["pct_hours_negative"] > ccfg.max_negative_hour_fraction:
            reason = (f"funding negative {realized['pct_hours_negative']:.0%} of "
                      f"recent hours — not a reliable payer")
        elif net < ccfg.min_net_apr:
            reason = f"net APR {net:.1%} below {ccfg.min_net_apr:.0%} hurdle"

        out.append(CarryCandidate(
            coin=coin,
            mark_price=snap.mark_price,
            current_apr=snap.funding_apr,
            realized_apr_30d=realized["mean_apr"],
            expected_apr=expected,
            net_apr=net,
            pct_hours_negative=realized["pct_hours_negative"],
            open_interest_usd=snap.open_interest_usd,
            day_volume_usd=snap.day_volume_usd,
            disqualified=reason,
        ))
    out.sort(key=lambda c: c.net_apr, reverse=True)
    return out


def _disqualified(coin: str, reason: str) -> CarryCandidate:
    return CarryCandidate(coin=coin, mark_price=0.0, current_apr=0.0,
                          realized_apr_30d=0.0, expected_apr=0.0, net_apr=0.0,
                          pct_hours_negative=1.0, open_interest_usd=0.0,
                          day_volume_usd=0.0, disqualified=reason)


def build_plan(candidates: list[CarryCandidate], cfg: Config) -> CarryPlan:
    """Turn the ranked candidates into one concrete action.

    Split of the sleeve between the two legs: the spot leg IS the position
    (it earns nothing but the hedge), the perp margin is the buffer that
    keeps the short alive. We put ~45% into spot, keep ~55% as USDC margin
    against an equal-to-spot short — i.e. perp leverage < 1x, liquidation
    roughly a +80% move away. Boring by construction.
    """
    sleeve = cfg.carry_equity
    tradeable = [c for c in candidates if c.disqualified is None]

    if sleeve < cfg.carry.min_viable_equity_usd:
        return CarryPlan(
            action="accumulate", coin=None, sleeve_equity_usd=sleeve,
            spot_notional_usd=0.0, perp_short_notional_usd=0.0,
            perp_margin_usd=sleeve, perp_leverage=0.0,
            est_liquidation_price=None, expected_net_apr=0.0,
            expected_monthly_usd=0.0,
            notes=[
                f"Sleeve (${sleeve:.0f}) is below the ${cfg.carry.min_viable_equity_usd:.0f} "
                "viability floor: both legs can't clear the exchange minimum with a "
                "sane margin buffer. Hold USDC and add next month's deposit.",
            ],
        )

    if not tradeable:
        reasons = [f"{c.coin}: {c.disqualified}" for c in candidates]
        return CarryPlan(
            action="hold_usdc", coin=None, sleeve_equity_usd=sleeve,
            spot_notional_usd=0.0, perp_short_notional_usd=0.0,
            perp_margin_usd=sleeve, perp_leverage=0.0,
            est_liquidation_price=None, expected_net_apr=0.0,
            expected_monthly_usd=0.0,
            notes=["No coin clears the carry hurdles right now. Holding USDC "
                   "and earning nothing beats paying to be hedged."] + reasons,
        )

    best = tradeable[0]
    spot_notional = round(sleeve * 0.45, 2)
    perp_margin = round(sleeve - spot_notional, 2)
    short_notional = spot_notional            # delta-neutral: legs match
    leverage = short_notional / perp_margin
    liq = carry_liquidation_buffer(best.mark_price, leverage,
                                   HL_MAINTENANCE_MARGIN_APPROX)
    monthly = short_notional * best.net_apr / 12.0
    return CarryPlan(
        action="enter", coin=best.coin, sleeve_equity_usd=sleeve,
        spot_notional_usd=spot_notional,
        perp_short_notional_usd=short_notional,
        perp_margin_usd=perp_margin,
        perp_leverage=round(leverage, 2),
        est_liquidation_price=round(liq, 2),
        expected_net_apr=best.net_apr,
        expected_monthly_usd=round(monthly, 2),
        notes=[
            f"Funding is earned on the SHORT notional (${short_notional:.2f}), "
            f"not the whole sleeve — expected ~${monthly:.2f}/month at "
            f"{best.net_apr:.1%} net APR. Sleeve-level yield is roughly "
            f"0.45x the funding APR; that capital-efficiency haircut is the "
            "price of the margin buffer keeping the short safe.",
            f"Exit rule: close both legs if trailing 7-day funding APR < "
            f"{cfg.carry.exit_apr:.0%} (check with `two-sleeve scan`).",
            f"Rebalance rule: if {best.coin} rises so the perp loses >20% of its "
            "margin, move USDC from spot side or wallet into perp margin. Legs "
            "stay matched; only the buffer moves.",
        ],
    )
