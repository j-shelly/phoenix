"""Read-only Hyperliquid market-data client.

Everything here uses the PUBLIC info endpoint — no API key, no wallet, no
signing. It cannot touch funds. (Live order placement, if you ever want it,
lives behind the official `hyperliquid-python-sdk` and is deliberately not
wired in here — see docs/going-live.md.)

API shape: one endpoint, POST https://api.hyperliquid.xyz/info, with a JSON
body whose "type" field selects the query. Docs:
https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

MAINNET_URL = "https://api.hyperliquid.xyz/info"
TESTNET_URL = "https://api.hyperliquid-testnet.xyz/info"

# Hyperliquid pays funding every hour; rates in the API are per-hour decimals.
FUNDING_INTERVALS_PER_YEAR = 24 * 365


@dataclass(frozen=True)
class PerpSnapshot:
    """One perp market's current state, from metaAndAssetCtxs."""

    coin: str
    mark_price: float
    mid_price: float | None
    oracle_price: float
    funding_hourly: float          # current hourly funding rate (decimal)
    premium: float                 # perp premium vs oracle (decimal)
    open_interest_usd: float
    day_volume_usd: float
    max_leverage: int
    prev_day_price: float

    @property
    def funding_apr(self) -> float:
        """Current funding, simple-annualized. 0.0000125/hr -> ~0.1095 (10.95%)."""
        return self.funding_hourly * FUNDING_INTERVALS_PER_YEAR

    @property
    def day_change(self) -> float:
        if self.prev_day_price == 0:
            return 0.0
        return self.mark_price / self.prev_day_price - 1.0


class HyperliquidPublic:
    """Thin wrapper over the public info endpoint with retries and no state."""

    def __init__(self, base_url: str = MAINNET_URL, timeout: float = 10.0,
                 retries: int = 3, session: requests.Session | None = None):
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.session = session or requests.Session()

    def _post(self, body: dict[str, Any]) -> Any:
        last_err: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self.session.post(self.base_url, json=body, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as e:
                last_err = e
                if attempt < self.retries - 1:
                    time.sleep(2.0 ** attempt)
        raise ConnectionError(f"info request {body.get('type')} failed: {last_err}") from last_err

    # ---- raw queries -------------------------------------------------------

    def all_mids(self) -> dict[str, float]:
        raw = self._post({"type": "allMids"})
        return {coin: float(px) for coin, px in raw.items()}

    def meta_and_asset_ctxs(self) -> tuple[list[dict], list[dict]]:
        meta, ctxs = self._post({"type": "metaAndAssetCtxs"})
        return meta["universe"], ctxs

    # The API caps fundingHistory responses at 500 entries (~20.8 days of
    # hourly rates), so a 30-day request silently truncates without paging.
    FUNDING_PAGE_CAP = 500

    def funding_history(self, coin: str, start_ms: int, end_ms: int | None = None) -> list[dict]:
        out: list[dict] = []
        cursor = start_ms
        while True:
            body: dict[str, Any] = {"type": "fundingHistory", "coin": coin,
                                    "startTime": cursor}
            if end_ms is not None:
                body["endTime"] = end_ms
            batch = self._post(body)
            out.extend(batch)
            if len(batch) < self.FUNDING_PAGE_CAP:
                return out
            cursor = int(batch[-1]["time"]) + 1

    def candles(self, coin: str, interval: str, start_ms: int, end_ms: int) -> list[dict]:
        """interval: "1m","5m","15m","1h","4h","1d",... Returns bars with keys
        t (open time ms), o/h/l/c (strings), v (volume in base units)."""
        return self._post({
            "type": "candleSnapshot",
            "req": {"coin": coin, "interval": interval,
                    "startTime": start_ms, "endTime": end_ms},
        })

    def spot_meta_and_asset_ctxs(self) -> tuple[dict, list[dict]]:
        meta, ctxs = self._post({"type": "spotMetaAndAssetCtxs"})
        return meta, ctxs

    # ---- convenience -------------------------------------------------------

    def perp_snapshots(self) -> list[PerpSnapshot]:
        """Current state of every listed perp, joined from meta + contexts."""
        universe, ctxs = self.meta_and_asset_ctxs()
        out: list[PerpSnapshot] = []
        for asset, ctx in zip(universe, ctxs):
            if asset.get("isDelisted"):
                continue
            mark = float(ctx["markPx"])
            oi_base = float(ctx.get("openInterest", 0.0))
            out.append(PerpSnapshot(
                coin=asset["name"],
                mark_price=mark,
                mid_price=float(ctx["midPx"]) if ctx.get("midPx") else None,
                oracle_price=float(ctx.get("oraclePx", mark)),
                funding_hourly=float(ctx.get("funding", 0.0)),
                premium=float(ctx["premium"]) if ctx.get("premium") else 0.0,
                open_interest_usd=oi_base * mark,
                day_volume_usd=float(ctx.get("dayNtlVlm", 0.0)),
                max_leverage=int(asset.get("maxLeverage", 1)),
                prev_day_price=float(ctx.get("prevDayPx", mark)),
            ))
        return out

    def funding_aprs_realized(self, coin: str, days: int = 30) -> dict[str, float]:
        """Realized (historical) funding for `coin` over the last `days`,
        summarized as annualized rates. This is the honest number for the
        carry sleeve — current funding is one hour's mood; the trailing
        average is the yield you'd actually have earned.
        """
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - days * 24 * 3600 * 1000
        hist = self.funding_history(coin, start_ms, now_ms)
        rates = [float(h["fundingRate"]) for h in hist]
        if not rates:
            return {"mean_apr": 0.0, "min_apr": 0.0, "max_apr": 0.0,
                    "pct_hours_negative": 0.0, "hours": 0}
        mean_hourly = sum(rates) / len(rates)
        return {
            "mean_apr": mean_hourly * FUNDING_INTERVALS_PER_YEAR,
            "min_apr": min(rates) * FUNDING_INTERVALS_PER_YEAR,
            "max_apr": max(rates) * FUNDING_INTERVALS_PER_YEAR,
            "pct_hours_negative": sum(1 for r in rates if r < 0) / len(rates),
            "hours": len(rates),
        }

    def daily_bars(self, coin: str, days: int) -> tuple[list[float], list[float], list[float], list[float]]:
        """(highs, lows, closes, volumes) from COMPLETED daily candles,
        oldest first. Volume is in base units — only meaningful relative to
        itself.

        The still-forming current-day (UTC) candle is dropped: its close is
        just the live price and its volume covers only part of a day, so
        signals computed on it would appear and vanish with the wall clock
        and the breakout volume filter would compare a partial day against
        full-day averages.
        """
        now_ms = int(time.time() * 1000)
        day_ms = 24 * 3600 * 1000
        start_ms = now_ms - (days + 2) * day_ms
        bars = self.candles(coin, "1d", start_ms, now_ms)
        bars.sort(key=lambda b: b["t"])
        bars = [b for b in bars if int(b["t"]) + day_ms <= now_ms]
        highs = [float(b["h"]) for b in bars]
        lows = [float(b["l"]) for b in bars]
        closes = [float(b["c"]) for b in bars]
        volumes = [float(b["v"]) for b in bars]
        return highs, lows, closes, volumes
