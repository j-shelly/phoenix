# two-sleeve

A learning-first crypto trading system for a $100/month experimental account,
built around [Phoenix Perpetuals](https://www.phoenix.trade/) (the product
being tested) and [Hyperliquid](https://app.hyperliquid.xyz/) (where the
conservative sleeve's machinery lives).

**Sleeve 1 — "carry" (80% of funds).** Delta-neutral funding-rate
harvesting: hold spot, short the same amount of perp, collect the hourly
funding payments while being (almost) indifferent to price. Targets
high-single-digit annualized yield *when the market pays it* and sits in
USDC when it doesn't. Boring by construction.

**Sleeve 2 — "venture" (20% of funds).** Small, strictly-capped high-risk
trades: Donchian breakouts with ATR trailing stops, sized so the sleeve can
die over a month of trades but never in one. This sleeve's real product is
the trade journal and what you learn from it. Expected value: tuition.

The system runs in **advisor mode**: it reads public market data (no keys,
no custody, it cannot touch funds) and prints exactly what to do in the
exchange UI. You click. That's deliberate — see `docs/going-live.md` for
the graduation ladder to automation.

## Honest expectations, before anything else

* **"Conservative ~8%" means ~8% per YEAR.** 8% per *month* is 152%
  annualized; nothing conservative pays that, on any venue, ever. On $80,
  8%/yr is about **$6.40** — the point of year one is process, not income.
* **As of August 2026 even 8%/yr is not reliably on offer** from this
  trade: BTC is ~49% below its Oct 2025 high, funding spent much of H1 2026
  *negative* (a 46-day streak), and sat at roughly 6–11% annualized on
  BTC/ETH in late July. The scanner enforces a "≥7% net or hold USDC"
  hurdle — expect it to say *hold USDC* some months. That is the strategy
  working, not failing.
* **The venture sleeve plays against brutal base rates**: roughly 86% of
  Hyperliquid perp traders lose money (median PnL −$67), and across retail
  perp/day-trading studies 70–97% lose. Our edge is not cleverness — it's
  tiny size, hard risk caps, journaling, and quitting each month at a
  pre-committed loss budget.
* Everything here can go to zero: exchange failure, USDC depeg, bridge
  hacks, smart-contract bugs. Only fund this with the $100/month you were
  given to burn. **None of this is financial advice.**

## Quickstart (Ubuntu / WSL / any Linux or macOS)

Modern Ubuntu (23.04+, including WSL) marks the system Python "externally
managed" (PEP 668), so a bare `pip install` fails with
`error: externally-managed-environment`. Use the repo's virtual-env setup —
it's the right way on every platform anyway:

```bash
sudo apt update && sudo apt install -y python3-venv   # Ubuntu/WSL only, once
./scripts/setup.sh          # creates .venv/, installs, runs the tests
source .venv/bin/activate   # repeat in each new shell (or use .venv/bin/two-sleeve)

two-sleeve scan             # funding board + Fear&Greed: is carry being paid?
two-sleeve plan             # today's instructions for both sleeves
two-sleeve explain funding  # start here; then: carry, sizing, liquidation, fees
two-sleeve report           # your PnL, win rate, and loss-budget status
```

<details>
<summary>Manual equivalent, if you prefer to see every step</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -q  # all tests should pass
```
</details>

**WSL note:** WSL2's clock can drift after your laptop sleeps, and the
scanner's "completed daily candle" logic uses system time. If `scan`/`plan`
ever look stale after a resume, run `sudo hwclock -s` (or `wsl --shutdown`
from Windows) to resync.

`two-sleeve plan` output is written in UI-click terms, e.g.:

```
== SLEEVE 1: carry (80%) ==
ACTION: enter ETH carry
  1. On Hyperliquid SPOT: buy $36.00 of ETH
  2. On Hyperliquid PERPS: with $44.00 USDC margin, SHORT $36.00 of ETH-PERP (0.82x, isolated)
  3. Estimated liquidation on the short: ~4,180.00 (price must rise that far against you)
  Expected: ~7.9% net APR ≈ $0.24/month at this size
```

## The monthly rhythm

| When | What | Command |
|---|---|---|
| Deposit day | $100 arrives → $80 carry / $20 venture. Rebalance sleeves to 80/20 | `two-sleeve plan` |
| Daily (2 min) | Check for fresh venture signals; manage stops on open trades | `two-sleeve plan` |
| Weekly (15 min) | Carry health: funding still paying? margin buffer OK? Journal review | `two-sleeve scan`, `report` |
| Monthly | Grade the month: sleeve PnL, lessons, one config improvement | `two-sleeve report` |
| Event days | Flatten/halve venture positions before FOMC & CPI prints | calendar in `docs/strategy.md` |

## Where each sleeve trades and why

* **Sleeve 1 → Hyperliquid**: carry needs spot AND perp in one venue;
  Hyperliquid has real spot books for BTC/ETH/SOL (Unit-bridged UBTC/UETH/
  USOL) next to its perps. A Solana-native variant (spot in your wallet +
  short on Phoenix) exists for month 1 before bridging is worth it — see
  `docs/strategy.md`.
* **Sleeve 2 → Phoenix**: you're being paid to test it, taker fees are
  ~22% cheaper than Hyperliquid's base tier (0.035% vs 0.045%), and the
  signals from `two-sleeve plan` (computed on Hyperliquid's free data) are
  for coins listed on both venues (BTC, ETH, SOL, DOGE, XRP, HYPE).
  Bonus: Phoenix's official `vulcan` CLI has a **paper-trading mode with
  live prices** — rehearse there first, it's free.

## Reading list (in order)

1. `two-sleeve explain funding` → `carry` → `sizing` → `liquidation` → `fees`
2. `docs/strategy.md` — the full design with researched numbers and every risk
3. `docs/month-1-checklist.md` — literally what to do in week 1-4
4. `docs/venues.md` — Phoenix & Hyperliquid mechanics, fee tables, scam warning
5. `docs/going-live.md` — the advisor → automation ladder

## Repo map

```
two_sleeve/
  indicators.py    pure signal math (EMA, ATR, Donchian, RSI, funding APR)
  risk.py          position sizing + kill switch — the most important file
  carry.py         sleeve 1 engine: funding scanner, net-APR hurdles, plan builder
  venture.py       sleeve 2 engine: breakout/breakdown signals, funding-fade (off)
  hyperliquid.py   read-only public-API client (no keys anywhere in this repo)
  sentiment.py     Fear & Greed regime dial
  ledger.py        append-only trade journal (~/.two-sleeve/ledger.jsonl)
  cli.py           scan / plan / report / log / explain
docs/              strategy, venues, month-1 checklist, going-live
tests/             offline test suite (fake exchange fixtures)
```

State (journal + config overrides) lives in `~/.two-sleeve/` by default;
set `TWO_SLEEVE_DATA_DIR` to relocate it (e.g. `TWO_SLEEVE_DATA_DIR=./data`
to keep it inside a checkout). `report` and `log` print the path in use.
