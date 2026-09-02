# From advisor to automation — the graduation ladder

This repo ships in **advisor mode** on purpose: it reads public market data,
computes exactly what to do, and you click the buttons. That is not a
limitation, it's the curriculum. Automate a strategy you haven't run by hand
and you've automated your own ignorance.

The ladder — spend at least a couple of weeks on each rung:

## Rung 0 — paper (week 1+)
* `two-sleeve plan` daily; journal the trades it suggests with
  `two-sleeve log open ... ` (they default to `[paper]`).
* On Phoenix: `vulcan paper init --balance 10000` and rehearse the venture
  trades with live prices and zero risk.
* Graduate when: two weeks of journaled paper trades and you can explain
  every line of `two-sleeve explain carry` to a friend.

## Rung 1 — manual real money (month 1-2)
* Real deposits, UI clicks, tiny sizes. `--real` flag on your journal
  entries. The journal IS the product of this phase.
* Graduate when: one full month including a funding payment on the carry
  short, at least 3 venture trades with stops honored, zero "oops" clicks.

## Rung 2 — semi-automation: alerts, not orders (month 2-3)
* Cron the scanner so it emails/notifies instead of you remembering.
  Cron does NOT activate virtual environments, so call the venv's binary
  by absolute path:
  `0 13 * * * $HOME/phoenix/.venv/bin/two-sleeve plan > /tmp/plan.txt 2>&1`
  (then pipe to mail, a Discord webhook, whatever). On WSL, cron isn't
  running unless you've enabled systemd or started it (`sudo service cron
  start`); a Windows Task Scheduler job running
  `wsl -e $HOME/phoenix/.venv/bin/two-sleeve plan` is often easier.
  The human still places orders.
* This is also where you can wire `vulcan`'s MCP server into Claude Code
  and ask it to check Phoenix state conversationally.

## Rung 3 — automated execution (month 3+, optional)
Only worth it if rungs 0-2 showed the process works and the clicking is the
bottleneck. What it takes, on each venue:

**Hyperliquid** (`.venv/bin/pip install -e '.[live]'` pulls the official
`hyperliquid-python-sdk`):
1. Create an **API/agent wallet** (`Exchange.approve_agent()` or the app's
   API page). Agent wallets can sign orders but **cannot withdraw funds** —
   this is the permission model you want. Never put your master key on a
   server.
2. Keep the agent key in an environment variable or OS keychain, never in
   the repo (`.gitignore` already refuses `.env` and `*.key`).
3. Respect the address-based action limit (1 action per $1 volume + 10k
   buffer): a tiny account that spams cancel/replace will rate-limit
   itself. Place resting orders and leave them alone.
4. Rehearse the full loop on **testnet** first
   (api.hyperliquid-testnet.xyz + faucet).

**Phoenix**: no official Python SDK for perps; automate via the TypeScript
SDK (`@ellipsis-labs/rise`) or drive `vulcan` from scripts (it has JSON
output and strategy runners — TWAP, grid — built in).

## Non-negotiables at every rung
* The venture sleeve's kill switch (monthly loss budget) applies to bots
  doubly: a bot can lose the budget at 3am without waking you.
* Any automated component gets its own sub-account/wallet holding ONLY the
  capital it manages.
* Log every action the bot takes to the same ledger you use by hand —
  one journal, human and machine entries side by side.
