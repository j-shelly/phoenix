# The two-sleeve strategy — full design

*Research date: Aug 7, 2026. Everything market-dependent below is stamped
with that date; re-verify numbers before acting on them. Not financial
advice; this is a learning system for money you can afford to lose.*

## 0. The regime you're deploying into (Aug 2026)

* BTC ≈ $64.7k, **−49% from the Oct 2025 high** ($126k). ETH ≈ $1.9k
  (−68%). SOL ≈ $73 (−74%). HYPE ≈ $56 — the one relative-strength major
  (+79% in Q2 2026), with a **~$790M token unlock on Aug 29**.
* **Funding was negative for much of H1 2026** (a 46-day negative streak on
  BTC's 30-day average — longest since 2020) and by late July was modestly
  positive: BTC ~6.4%, ETH ~11% annualized on Hyperliquid.
* **Volatility is at multi-year lows** (Deribit DVOL ~35 vs ~90 earlier in
  2026), Fear & Greed neutral (~44–49). Compressed vol + crowded shorts =
  squeeze fuel in both directions.
* Catalyst cluster after a quiet August: **Jackson Hole Aug 27–29 → HYPE
  unlock Aug 29 → CLARITY Act Senate window from Sept 14 → FOMC (with dot
  plot) Sept 15–16.** Fed funds 3.50–3.75%, so T-bills pay ~3.6% — the
  hurdle any crypto "yield" must beat to be worth its risks.

**Implication for sleeve 1:** this is a carry-unfriendly-to-neutral regime.
The scanner will often say "hold USDC" and it will be right.
**Implication for sleeve 2:** breakout systems starve in chop and feast on
vol expansion; the September catalyst cluster is where the interesting
trades likely live. Symmetric long/short matters — half of 2026's trends
have been down.

## 1. Sleeve 1 — carry (80% of funds)

### The trade

Short a perp, hold the same dollar amount of spot. Price risk nets out;
you keep the hourly funding stream while it's positive. Hyperliquid's
funding formula includes a fixed interest component (0.01% per 8h ≈ 11%
APR baseline paid to shorts in calm bull tape) plus a premium term, capped
at 4%/hour, settled hourly in USDC to your perp margin balance.

### The math that headline APRs hide

Funding is paid on **position notional**, not on your sleeve. With spot and
perp balances separate (they are, below $10k account value — Hyperliquid's
portfolio margin requires >$10k), an $80 sleeve deploys ~$36 in each leg
with the rest as margin buffer:

```
sleeve yield ≈ funding APR × (short notional / sleeve equity) ≈ funding APR × 0.45
```

So the sleeve needs **~15–18% funding APR to make 7–8% on capital** —
levels seen in bull regimes, not today's. At today's ~6–11% funding, the
sleeve earns ~3–5%. The config's `min_net_apr = 0.07` (≈2× T-bills) is the
"is this worth doing at all" gate on the *blended, fee-amortized* estimate.

Fees: full round trip on both legs, all taker ≈ **0.23%** of leg notional
(spot 0.07% + perp 0.045%, ×2). Amortized over the target ~45-day hold
that's ~1.9% APR of drag — priced into the scanner's `net_apr`.

### Rules (enforced or checked by `two-sleeve plan`)

1. **Enter** the top-ranked coin only when: blended funding (75% weight on
   30-day realized, 25% on current) minus fee drag ≥ **7% APR**; funding
   negative in <35% of recent hours; open interest and daily volume ≥ $10M.
2. **Structure**: 45% of sleeve in spot, 55% as USDC margin against an
   equal-to-spot short → **~0.8x leverage**, liquidation ≈ +80% away.
   Isolated margin, so the blast radius is the position.
3. **Rebalance**: if price rallies enough that the perp side loses >20% of
   its margin, top up margin from the spot side or wallet. Legs stay equal.
4. **Exit** both legs when trailing 7-day funding APR < **5%**, or on any
   structural red flag (ADL event on the venue, USDC stress, Unit bridge
   incident).
5. **When nothing qualifies: hold USDC.** Not earning is a position;
   paying to be hedged is not.

### Two ways to hold the spot leg

* **Classic (Hyperliquid-only)** — buy UBTC/UETH/USOL on HL spot, short
  the matching perp. One venue, one screen, cleanest ops. Cost: USDC must
  reach Hyperliquid (Arbitrum route; budget a few dollars and note the
  ~2–3% drag that bridging adds to an $80/month flow — it amortizes away
  as the sleeve grows).
* **Solana-native (month-1 friendly)** — buy SOL (or another Phoenix-listed
  major) with USDC in your own wallet via Jupiter or legacy.phoenix.trade,
  and short the same notional on **Phoenix perps** (isolated, ≤1x). No
  bridge, tests the product you're paid to test, Phoenix taker fee is
  cheaper (0.035%). Cost: funding rates on a young venue are less
  documented — read the live rate in the Phoenix UI before entering, and
  cross-check `two-sleeve scan`'s Hyperliquid rates for the same coin.

### If the scanner says "hold USDC" for months (realistic menu, Aug 2026)

| Option | Researched recent yield | Catch |
|---|---|---|
| Hold USDC, wait | 0% | none — and that's sometimes the best line on this table |
| HLP vault (Hyperliquid) | ~10–13% avg post-2025, lumpy, 5–12% drawdowns | full platform risk, 4-day lock, not principal-protected |
| Aave v3 USDC (Arbitrum/Base) | ~4–5% | smart-contract risk, off-venue |
| Ethena sUSDe | ~4–8% in 2026 | someone else runs this same carry trade for you; peg/custodian risk |

A defensible boring split while carry doesn't pay: keep the sleeve in USDC
and optionally put **up to half** into HLP with eyes open about what it is
(you're bankrolling the venue's market-maker/liquidator). Never put the
whole sleeve in any single yield wrapper.

### Full risk register (memorize the left column)

| Risk | Reality check | Mitigation |
|---|---|---|
| Funding flips negative | 46-day streak in 2026; whole quarters can pay ~0 | exit rule at 5%; hurdle at 7% |
| Short-leg liquidation in a melt-up | at 0.8x, needs ~+80% before trouble | leverage cap, weekly check, top-up rule |
| ADL (exchange force-closes your profitable short) | happened on HL Oct 10, 2025 | small size, accept as tail risk, re-hedge if it fires |
| Basis moves against exit | perp can trade under spot in stress | exit with limit orders, don't panic-market-out |
| Fee churn | round trip ≈ 3 weeks of carry at 5% APR | hold 45+ days, maker orders when possible |
| Unit bridge risk (UBTC/UETH/USOL) | MPC guardian custody behind HL spot majors | prefer SOL-native variant or smallest viable size |
| USDC depeg | traded $0.87 in Mar 2023 | accepted; this whole system is USDC-denominated |
| Venue risk (either exchange) | validator interventions have happened (JELLY, Mar 2025) | never hold more here than the experiment's budget |

## 2. Sleeve 2 — venture (20% of funds)

### What the evidence supports (and what it doesn't)

* **Time-series momentum / Donchian breakouts on majors** are the most
  evidence-backed retail-feasible approach: ~30–40% win rates with winners
  3–5× losers. All profit comes from letting rare winners run → the
  trailing stop *is* the strategy. Chandelier-style **2.5×ATR** trailing
  stops beat tight/fixed stops in backtests by wide margins.
* **Low-volume breakouts fail disproportionately** → volume filter
  (breakout bar > 20-bar average volume) is enforced in the scanner.
* **Funding extremes and Fear & Greed extremes work as filters, not
  triggers.** A May 2026 SSRN study found *no* exploitable cross-sectional
  alpha from funding signals after costs — so the funding-fade module ships
  **disabled** (`fade_enabled: false`); watch its would-be signals for a
  month before ever enabling it.
* **Event days**: BTC vol on FOMC days runs 50–100% above normal. We don't
  predict direction; we **flatten or halve positions before FOMC and CPI**
  and let the vol expansion hit other people's stops.
* **Base rates**: ~86% of Hyperliquid perp traders lose; 27% of small
  accounts lose >85% within 30 days. Sleeve 2's honest expected value is
  negative. It exists to buy reps, journal entries, and product knowledge
  at a fixed, pre-paid price ($20/month).

### Rules (enforced by the engine)

1. Universe: BTC, ETH, SOL, HYPE, DOGE, XRP — liquid majors only, listed
   on both Phoenix and Hyperliquid. No thin alts, ever, at this size.
2. Entry: fresh 20-day Donchian breakout (close beyond yesterday's
   channel) in the direction of the 50-day EMA, RSI < 80, volume confirmed.
   Both directions — breakdown shorts count (half of 2026 trended down).
3. Stop: 2.5×ATR from entry, trailed (never widened). If the stop is hit,
   you're out, no debate — the journal's `--lesson` field is the only
   permitted response.
4. Size: risk **30% of the sleeve per trade** (`risk.py` computes notional
   from stop distance; refuses trades that would breach the $10 exchange
   minimum by sizing *down* to zero, never up). Max 2 concurrent trades.
   Leverage cap 3x — beyond that, fees × leverage + liquidation mechanics
   make the exchange your counterparty, not the market.
5. Monthly kill switch: when the sleeve's losses reach the month's budget
   (the whole $20), it stops opening trades until next deposit. Several
   small deaths, never one big one.
6. No trade is the default state. Some weeks `plan` prints nothing. Chop
   eats breakout traders; patience is the edge retail actually has.

### Near-term calendar (from the Aug 2026 research)

| Date | Event | Sleeve-2 posture |
|---|---|---|
| Aug 27–29 | Jackson Hole symposium | no new entries day-of; expect vol |
| Aug 29 | HYPE ~14.2M token unlock (~$790M) | no HYPE longs into it; a breakdown signal after it would be "textbook" |
| from Sept 14 | CLARITY Act Senate window | headline risk both ways |
| Sept 15–16 | FOMC + dot plot | flatten or halve before 2pm ET Wed |

## 3. Capital schedule and what to measure

Month 1: $100 → carry sleeve $80 (above the $60 viability floor — deploy
if funding qualifies; else USDC/menu), venture $20 (≈3 trades of $6 risk).
Every month adds $100 split 80/20; by month 6 the carry sleeve is ~$480
and its dollar yield starts being visible instead of theoretical.

Measure, monthly, in `two-sleeve report` terms:

* Carry: realized funding collected vs. the USDC-do-nothing baseline; number
  of days deployed vs. parked (deployment discipline, not yield, is the KPI
  in year one).
* Venture: trades taken, % with stops honored (target: 100%), average
  loss ≤ planned risk, lessons journaled per trade (target: 1.0).
* Both: zero unforced errors — wrong venue, wrong size, missed stop,
  position forgotten over a weekend.

## 4. What "~8%" actually means here

The 8% target is **annualized, on sleeve-1 capital, conditional on the
market paying for carry**. The honest Aug-2026 decomposition:

```
funding APR needed for 8% on sleeve  ≈ 8% / 0.45 deployment ≈ 17.8%
funding APR actually on offer (BTC)  ≈ 6.4%  → sleeve earns ~2.9% if deployed
scanner's verdict at these levels    → likely "hold USDC" / take the menu
```

If the cycle turns and funding revisits its bull-market 15–30% range (as in
2024), the same machinery — already built, tested, and rehearsed — earns
its 8%+ without a single line of code changing. Positioning for that while
risking almost nothing in the meantime is the whole design.
