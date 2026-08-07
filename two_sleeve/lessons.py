"""Mini-lessons for `two-sleeve explain <topic>`.

Each one is meant to be read in under two minutes, ideally right before the
concept matters. They are opinionated on purpose.
"""

LESSONS: dict[str, str] = {
    "funding": """\
FUNDING — the heartbeat of every perp market

A perpetual future never expires, so nothing forces its price back to spot.
Exchanges solve this with funding: every hour, one side pays the other a
small percentage of position size.

  perp trading ABOVE spot  -> longs pay shorts   (funding positive)
  perp trading BELOW spot  -> shorts pay longs   (funding negative)

The rate looks tiny — 0.00125%/hour is typical — but it compounds:
0.00125%/hr x 24 x 365 ~= 11%/year. That's the entire engine of sleeve 1.

Read it two ways:
  * as YIELD: positive funding pays anyone short. Hedge the price risk and
    it's income (see `explain carry`).
  * as SENTIMENT: extreme funding = a crowded side paying desperately to
    stay in. Crowds that pay to hold a position usually get squeezed.
""",
    "carry": """\
CARRY — getting paid to be boring

The trade: SHORT the perp, BUY the same dollar amount of spot.

  price rises  -> spot gains, perp short loses  -> net ~zero
  price falls  -> spot loses, perp short gains  -> net ~zero
  every hour   -> if funding is positive, your short GETS PAID

You've removed the price bet and kept the income stream. This is the same
skeleton as classic cash-and-carry in futures markets.

Ways it goes wrong (memorize these, they're the whole risk section):
  1. Funding flips negative and stays -> your income becomes an expense.
     Cure: exit rule on trailing 7-day funding.
  2. Perp short gets liquidated in a violent rally, leaving you naked long
     spot. Cure: low leverage (~1x) and topping up margin on big rallies.
  3. Fees eat the yield if you churn. Cure: enter rarely, hold weeks.
Note the trade pays on the SHORT NOTIONAL, and roughly half the sleeve is
sitting in margin/buffer — so a 10% funding APR is ~5% on the sleeve. That's
why the hurdle math in the config matters.
""",
    "sizing": """\
SIZING — the only edge a beginner actually controls

The fixed-fractional rule: decide what fraction of your equity a losing
trade may cost you (sleeve 2 uses 30% of the sleeve). Then:

  notional = risk_dollars x entry / |entry - stop|

The stop distance comes from volatility (2 x ATR), not from a round number.
Consequences worth internalizing:
  * Wider stop -> SMALLER position, same risk. Vol decides size, not vibes.
  * The exchange minimum ($10 on Hyperliquid) is a floor on notional. If
    correct sizing lands under it, the trade is refused. Never size UP to
    meet a minimum.
  * Leverage is not a strategy; it's a borrowing fee plus a liquidation
    price. Above ~3x on a small account, the house always wins eventually.
""",
    "liquidation": """\
LIQUIDATION — how perps actually kill accounts

Your margin is collateral against the position's losses. When losses eat
margin down to the maintenance requirement, the exchange force-closes you —
at the worst price, plus a penalty. You don't get to argue.

Rough math for a SHORT at leverage L, maintenance margin m:
  liquidation price ~= entry x (1 + 1/L - m)

  1x short: price must roughly DOUBLE before liquidation.  Calm.
  2x short: ~ +50%.  Survivable with weekly check-ins.
  5x short: ~ +19%.  BTC does that in a good week.
 20x short: ~  +4%.  You are the exit liquidity.

Sleeve 1 keeps its perp short near 1x for exactly this reason. Isolated
margin (per-position) beats cross for learning: the blast radius is one
position, not the account.
""",
    "fees": """\
FEES — the silent strategy-killer at small size

Hyperliquid base tier: perp taker 0.045%, spot taker ~0.07% (maker is
roughly 3x cheaper on perps). Feels like nothing. Now do the math on a $36
carry position:

  open + close both legs, all taker: 2x0.07% + 2x0.045% = 0.23% ~= $0.08.
  Trivial? Only if you hold. Flip the position weekly and it's ~1%/month —
  a third of your expected carry APR, gone.

Rules of thumb:
  * Enter seldom, hold long. The carry sleeve targets 45+ day holds.
  * Use resting (maker/limit) orders when you're not in a hurry.
  * Every venture trade should expect to pay ~0.1-0.3% round-trip in fees
    plus slippage — which is why we don't scalp with $20.
""",
    "basis": """\
BASIS — the other way perps drift from spot

Basis = perp price minus spot price. Funding is the rate; basis is the gap
itself. When you ENTER a carry (sell perp, buy spot) you actually want a
positive basis — you sell the expensive leg and buy the cheap one, pocketing
the gap as a tiny bonus when they reconverge. When basis is negative
(perp below spot), entering carry costs you that gap up front.

You don't need to optimize this at our size — but check the perp premium on
the scan before entering: strongly negative premium + positive funding is a
sign funding is about to flip.
""",
    "journal": """\
JOURNAL — the highest-Sharpe habit in trading

Nobody's first hundred trades are profitable enough to matter. Their journal
is what makes trades 101+ better. The ledger here forces two fields:

  --thesis on open:  what do you believe, and what would make it wrong?
  --lesson on close: what did the market teach you, in one sentence?

Review weekly. You're looking for patterns in YOUR behavior, not the
market's: do you cut winners early? widen stops when losing? revenge-trade
after a stop-out? Those three mistakes are ~80% of retail underperformance.
""",
}
