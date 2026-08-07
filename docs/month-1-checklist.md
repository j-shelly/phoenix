# Month 1 — literal checklist

First $100 is in hand. This month optimizes for setup, safety, and reps —
not returns. Check boxes in order.

## Week 1 — accounts, security, paper

- [ ] **Wallet hygiene first.** Create a FRESH Solana wallet (Phantom or
      Solflare) used only for this experiment. Write the seed phrase on
      paper, never in a file. This wallet never holds more than the
      experiment's money.
- [ ] Get a Phoenix **access/referral code** (waitlist on phoenix.trade, or
      a code from an existing user). Register, deposit **$20 USDC** +
      ~0.05 SOL for gas. Only trust `phoenix.trade` —
      `phoenix-trade.org` is a lookalike site; Phoenix has **no token**.
- [ ] Check the Terms of Use / any geo notices on the site yourself when
      you first connect (research found no published restricted-country
      list, but it was unverifiable from the sandbox).
- [ ] Install Phoenix's official CLI: `vulcan` (github.com/Ellipsis-Labs/
      vulcan-cli) → `vulcan paper init --balance 10000` → place 5 paper
      trades to learn order types (limit, market, stop) with zero risk.
- [ ] Install this repo: `pip install -e .` → run `two-sleeve scan` and
      `two-sleeve explain funding`. Read all seven lessons this week.
- [ ] Keep the remaining $80 as USDC in the wallet for now.

## Week 2 — first real venture trade (tiny), carry homework

- [ ] Run `two-sleeve plan` daily. If a venture signal appears: place it on
      Phoenix at HALF size the first time (~$3 risk). Journal BEFORE
      entering: `two-sleeve log open --sleeve venture --symbol ... --thesis "..."`.
      Set the stop-loss order in the UI at the price `plan` gives —
      Phoenix supports native stop orders; use them, don't "watch it".
- [ ] No signal? Take zero trades. Log what the scanner said anyway —
      "no trade" days build the patience muscle this sleeve exists to train.
- [ ] Carry homework: read the current funding rate for SOL/BTC/ETH in the
      Phoenix UI (and `two-sleeve scan` for Hyperliquid's). Are shorts
      being paid ≥7% annualized anywhere? Write down the answer and date.

## Week 3 — decide the carry question

- [ ] If `two-sleeve scan` shows a qualified coin (net APR ≥ 7%): enter the
      **Solana-native carry** at half size — buy ~$18 of the coin (Jupiter
      or legacy.phoenix.trade), short ~$18 notional on Phoenix isolated at
      ≤1x with ~$22 margin. Journal it (`--side carry`).
- [ ] If nothing qualifies (likely in Aug 2026): park the $80 as USDC and
      decide deliberately about the yield menu (docs/strategy.md §1) —
      HLP for up to half is the aggressive-boring option; all-USDC is the
      conservative-boring option. Write down which you chose and why.
- [ ] Watch one funding payment actually land (Phoenix pays hourly; the
      position row shows accrued funding). Seeing +$0.0003 arrive teaches
      more than any doc.

## Week 4 — close the loop

- [ ] Close or trail everything per the rules. Run `two-sleeve report`.
- [ ] Month-end journal review: every close has a `--lesson`. Read them
      all. Pick ONE process improvement for month 2 (e.g. "use maker
      orders", "stop checking prices hourly") — one, not five.
- [ ] Grade against docs/strategy.md §3 metrics: stops honored %, unforced
      errors (target 0), lessons per trade (target 1.0).
- [ ] If Flight Club (Phoenix's rewards program, live through ~Aug 23-24,
      2026) credited any USDC from your ordinary activity, note it as
      "rewards" income in the journal — and do NOT start churning volume
      to farm it.

## Standing rules — all four weeks

* Never market-buy into a spike; use limit orders.
* Nothing gets more than 3x leverage, ever, and carry shorts stay ≤1x
  this month.
* Before FOMC/CPI timestamps: no open venture positions (calendar in
  docs/strategy.md §2).
* If total losses this month hit $20, sleeve 2 is done until next deposit.
  The kill switch is a promise you made to yourself while calm.
* When in doubt, the correct position size is zero.
