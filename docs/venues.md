# Venue guide: Phoenix Perpetuals and Hyperliquid

Everything below was researched Aug 7, 2026. Exchange parameters drift —
fees, leverage caps and reward programs are moving targets. Verify the
numbers in the app before trading; the code reads what it can from public
APIs at runtime instead of trusting this file.

## Phoenix (www.phoenix.trade) — where your test funds arrive

**What it is.** "Phoenix Perpetuals" by Ellipsis Labs: a fully on-chain
perp-futures orderbook on **Solana mainnet** — orders, matching and
settlement all on-chain, non-custodial, ~0.5s finality. It is NOT the old
2023 Phoenix spot DEX; that still exists separately at legacy.phoenix.trade.

**⚠️ Impersonator warning.** `phoenix-trade.org` (talks about a "PHX token"
and staking) is a lookalike site. Phoenix has **no token**. Trust only
phoenix.trade, docs.phoenix.trade, @PhoenixTrade, github.com/Ellipsis-Labs.

| | Phoenix perps |
|---|---|
| Chain / wallet | Solana; Phantom, Solflare, Backpack, Ledger, any wallet-adapter wallet |
| Collateral | USDC only (canonical Solana USDC). SOL-as-collateral announced, not shipped |
| Markets | ~29: SOL, BTC, ETH, DOGE, SUI, XRP, BNB, AAVE, ZEC, HYPE… plus GOLD/SILVER/OIL perps on a CME calendar |
| Fees | **maker 0.005% / taker 0.035%** (per-market config — verify live) + Solana gas (keep ~0.05 SOL) |
| Funding | hourly |
| Margin | cross (subaccount 0) + isolated (subaccounts 1+) |
| Leverage | tiered per market, up to ~20-25x on majors (don't) |
| Min order | 1 base lot (≈$10 or less on majors; fetch per-market lot size) |
| Onboarding | needs an **access code or referral code**; waitlist on site |
| API | REST `https://perp-api.phoenix.trade`, WS `wss://perp-api.phoenix.trade/v1/ws`; docs.phoenix.trade/api |
| SDKs | TypeScript `@ellipsis-labs/rise`; Rust `phoenix-rise`; **no official Python SDK for perps** |

**The killer tool: `vulcan` CLI** (github.com/Ellipsis-Labs/vulcan-cli).
Official Phoenix CLI with market data, trading, portfolio — and two things
you should use immediately:

* **paper-trading engine with live prices, no wallet needed**:
  `vulcan paper init --balance 10000` — rehearse every strategy in this
  repo risk-free before spending a real dollar;
* a **local MCP server + Claude Code agent skills** — you can literally
  wire Phoenix into a Claude Code session and drive it conversationally.

**Rewards (as researched Aug 7, 2026):** "Flight Club" — 420,000 USDC over
28 days (15k USDC/day), launched ~Jul 27, so it runs to ~**Aug 23-24, 2026**.
Paid daily in USDC based on trading volume, open interest held, and
referrals. Your ordinary testing activity qualifies on its own — do NOT
churn trades just to farm volume; that's wash-trading-adjacent, the fees eat
you, and reward programs routinely disqualify it. Referral program: 20% of
referees' fees (10% second tier). No points system or token is announced;
airdrop speculation is exactly that.

## Hyperliquid (app.hyperliquid.xyz) — where the carry sleeve lives

Hyperliquid runs on its own L1. Crucially for us it has both **perps and
real spot markets** — including Unit-bridged majors **UBTC, UETH, USOL**
traded against USDC — which is what makes a single-venue spot-vs-perp carry
possible.

| | Hyperliquid |
|---|---|
| Deposit | USDC via Arbitrum (min 5 USDC; ~$1 flat withdrawal fee); native BTC/ETH/SOL via Unit |
| Perp fees (base tier) | maker 0.015% / taker 0.045% (4% referral discount available; verify via `userFees`) |
| Spot fees (base tier) | maker 0.040% / taker 0.070% |
| Funding | **hourly**, formula = premium + clamped interest component; the fixed interest component (0.01%/8h ≈ 11% APR) structurally favors shorts |
| Min order | **$10 notional** (perps and spot) |
| Leverage | per-asset, read from API (BTC ~40x max — again: don't) |
| API | `POST https://api.hyperliquid.xyz/info` public, no key needed — that's all this repo's tooling uses |
| Python SDK | `hyperliquid-python-sdk` (official) — needed only if you later automate execution |
| Testnet | app.hyperliquid-testnet.xyz + faucet (1000 mock USDC; requires a prior mainnet deposit) |

**Rate limits worth knowing:** 1200 weight/min per IP; `metaAndAssetCtxs`,
`fundingHistory` and `candleSnapshot` cost 20 each, `allMids` costs 2. One
`two-sleeve plan` run costs ~240 weight — you could run it four times a
minute, and you'll run it once a day.

**Native yield option:** the HLP vault (protocol market-making vault) has
returned roughly 10-25% annualized over trailing periods with real
drawdown risk and a 4-day lockup. It's a legitimate "boring-ish" USDC
parking spot, but it is NOT risk-free and NOT the same trade as carry —
see docs/strategy.md for how we use it (spoiler: as a fallback, small).

## Which sleeve trades where, and why

| | Venue | Why |
|---|---|---|
| Sleeve 1 (carry, 80%) | Hyperliquid — or Solana-native variant with spot in your wallet + short on Phoenix | needs spot AND perp; HL has both in one account. The Solana-native variant avoids bridging and tests Phoenix harder |
| Sleeve 2 (venture, 20%) | Phoenix | you're paid to test it; taker fees ~22% cheaper than HL; signals from `two-sleeve plan` are computed on HL data and the same coins (BTC/ETH/SOL/DOGE/XRP/HYPE) trade on both venues |

Money route each month: $100 USDC arrives on Solana → $20 stays on Phoenix
(sleeve 2 margin) → $80 either stays on Solana for the native carry variant
or bridges to Hyperliquid for the classic carry (bridge/CEX hop costs a few
dollars — at $80/month that ~2-3% drag is real; the strategy doc weighs it).
