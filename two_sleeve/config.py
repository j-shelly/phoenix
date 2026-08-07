"""All the knobs in one place, with the reasoning next to each knob.

Override anything by creating data/config.json with the fields you want to
change, e.g. {"total_equity_usd": 200, "carry": {"min_net_apr": 0.05}}.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_PATH = Path("data") / "config.json"


@dataclass
class Fees:
    """Exchange fees at base tier (no volume discounts, no staking discount).

    Hyperliquid: perp taker 0.045%, maker 0.015%; spot taker 0.070%,
    maker 0.040%. Phoenix perps: taker 0.035%, maker 0.005% (per-market
    config — verify live values in the app; also budget ~0.01 SOL/tx gas).
    At our size we assume TAKER everywhere — pessimistic on purpose. Using
    resting (maker) orders is one of the first optimizations you can learn.
    """

    perp_taker: float = 0.00045
    perp_maker: float = 0.00015
    spot_taker: float = 0.0007
    spot_maker: float = 0.0004
    phoenix_perp_taker: float = 0.00035
    phoenix_perp_maker: float = 0.00005

    @property
    def carry_round_trip(self) -> float:
        """Open+close both legs of a carry position, all taker:
        spot buy + spot sell + perp open + perp close."""
        return 2 * self.spot_taker + 2 * self.perp_taker


@dataclass
class CarryConfig:
    """Sleeve 1: delta-neutral funding harvest. 80% of capital."""

    allocation: float = 0.80
    # Don't enter unless expected NET apr (after fee amortization) clears this.
    # Rule of thumb from practitioner research: enter carry only when trailing
    # funding annualized > ~2x the T-bill rate (~3.6% in Aug 2026 -> ~7%).
    # Below it, doing nothing (holding USDC) is the better trade.
    min_net_apr: float = 0.07
    # Blend of instantaneous funding vs. trailing realized when estimating.
    # Realized dominates: current funding is one hour's mood.
    realized_weight: float = 0.75
    realized_days: int = 30
    # Skip coins whose funding was negative in too many recent hours.
    max_negative_hour_fraction: float = 0.35
    # Liquidity floors so we only carry things with a real market.
    min_open_interest_usd: float = 10_000_000.0
    min_day_volume_usd: float = 10_000_000.0
    # Perp short leg leverage cap. 1x = margin equals notional (safest).
    max_perp_leverage: float = 2.0
    # Exit if trailing 7-day realized funding drops under this.
    exit_apr: float = 0.05
    # Expected holding period for amortizing entry/exit fees into the APR.
    expected_hold_days: int = 45
    # Below this sleeve equity, both legs can't clear exchange minimums with
    # sane margin buffers -> accumulate USDC instead of forcing a tiny carry.
    min_viable_equity_usd: float = 60.0
    # Coins we're willing to carry (must have Hyperliquid spot to stay
    # single-venue). Extend as HL lists more spot majors.
    universe: tuple[str, ...] = ("BTC", "ETH", "SOL", "HYPE")


@dataclass
class VentureConfig:
    """Sleeve 2: high-risk learning trades. 20% of capital, may go to zero."""

    allocation: float = 0.20
    # Risk per trade as a fraction of the SLEEVE (not total equity).
    # 30% x ~3-4 trades a month = the sleeve can die in a month, by design,
    # but never in one trade.
    risk_per_trade: float = 0.30
    max_open_trades: int = 2
    max_leverage: float = 3.0
    # Donchian breakout lookback (days) and trailing stop width (ATRs).
    # 2.5x ATR per the Chandelier-exit evidence: wider stops that breathe with
    # volatility beat tight fixed stops on 30-40%-win-rate breakout systems.
    breakout_days: int = 20
    stop_atr_mult: float = 2.5
    atr_days: int = 14
    # Only take breakouts whose bar volume exceeds the 20-bar average —
    # low-volume breakouts fail disproportionately often.
    volume_confirm_bars: int = 20
    trend_ema_days: int = 50
    rsi_max_for_entry: float = 80.0
    # Funding-extreme fade thresholds (advanced signal, off by default).
    fade_enabled: bool = False
    fade_funding_apr: float = 0.40
    fade_zscore: float = 2.5
    # Only trade liquid perps.
    min_day_volume_usd: float = 25_000_000.0


@dataclass
class Config:
    total_equity_usd: float = 100.0
    # Exchange minimum order (Hyperliquid: $10 minimum order value).
    min_notional_usd: float = 10.0
    fees: Fees = field(default_factory=Fees)
    carry: CarryConfig = field(default_factory=CarryConfig)
    venture: VentureConfig = field(default_factory=VentureConfig)

    @property
    def carry_equity(self) -> float:
        return self.total_equity_usd * self.carry.allocation

    @property
    def venture_equity(self) -> float:
        return self.total_equity_usd * self.venture.allocation


def _apply_overrides(obj, overrides: dict) -> None:
    for key, value in overrides.items():
        if not hasattr(obj, key):
            raise KeyError(f"unknown config key: {key}")
        current = getattr(obj, key)
        if isinstance(value, dict) and hasattr(current, "__dataclass_fields__"):
            _apply_overrides(current, value)
        else:
            setattr(obj, key, value)


def load_config(path: Path = CONFIG_PATH) -> Config:
    cfg = Config()
    if path.exists():
        overrides = json.loads(path.read_text(encoding="utf-8"))
        _apply_overrides(cfg, overrides)
    return cfg


def save_config(cfg: Config, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
