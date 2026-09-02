"""Free sentiment/regime context. Currently one source: the Crypto Fear &
Greed Index (alternative.me), a daily 0-100 composite of volatility,
momentum, social chatter and dominance.

How we use it (and how we don't): F&G is a REGIME DIAL, not a trade signal.
Extreme fear (<20) historically precedes good 6-12 month returns — it says
"lean toward accumulation, distrust breakdown shorts". Extreme greed (>80)
says "distrust breakout longs, funding is probably rich". Nothing here
should ever place a trade on its own.
"""

from __future__ import annotations

import requests

FNG_URL = "https://api.alternative.me/fng/"


def fear_greed(timeout: float = 5.0) -> tuple[int, str] | None:
    """(value 0-100, classification) or None if unreachable. Never raises —
    sentiment is garnish, not a dependency."""
    try:
        resp = requests.get(FNG_URL, params={"limit": 1}, timeout=timeout)
        resp.raise_for_status()
        item = resp.json()["data"][0]
        return int(item["value"]), str(item["value_classification"])
    except Exception:
        return None
