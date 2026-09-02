# two-sleeve — repo guide for agents

Learning-first crypto trading system with two sleeves: `carry` (80%,
delta-neutral funding harvest, targets high-single-digit APR) and `venture`
(20%, capped high-risk momentum trades). Default mode is ADVISOR: code reads
public market data and prints instructions; the human clicks. There is no
order-execution code in this repo and none should be added casually — see
docs/going-live.md for the intended graduation path.

## Layout
- `two_sleeve/hyperliquid.py` — read-only public-API client (no keys anywhere)
- `two_sleeve/carry.py` / `venture.py` — the two sleeve engines
- `two_sleeve/yolo.py` — house-money degen mode (`two-sleeve yolo`); see below
- `two_sleeve/risk.py` — sizing + kill switch; touch with extreme care
- `two_sleeve/indicators.py` — pure math, fully unit-tested
- `two_sleeve/ledger.py` — append-only JSONL trade journal in `data/`
- `two_sleeve/cli.py` — `two-sleeve scan|plan|report|log|explain`
- `docs/` — strategy playbook, venue guide, month-1 checklist

## Conventions
- Python 3.10+, stdlib + `requests` only in core; heavier deps go behind
  extras in pyproject.
- Funding rates are HOURLY decimals; annualize via
  `indicators.annualize_hourly_funding` (×24×365). Don't invent new
  conventions.
- All USD amounts are floats named `*_usd`; rates/fractions are decimals
  (0.045% = 0.00045).
- User state (ledger + config overrides) lives in `~/.two-sleeve/` by
  default, overridable via `TWO_SLEEVE_DATA_DIR` (repo-local `data/` is
  gitignored for that case). Never commit state; `paths.py` is the single
  source of truth for its location.
- Tests: `python3 -m pytest tests/ -q`. Strategy changes need a test that
  pins the new behavior. Network-touching code gets a fake-client test.
- Never commit secrets; `.gitignore` blocks `.env`/`*.key` — keep it that way.

## Safety invariants (do not weaken silently)
- Sizing refuses trades below exchange minimum rather than sizing up.
- Venture risk is per-SLEEVE fraction with a monthly loss budget; carry perp
  leverage stays ≤ 2x.
- Exchange parameters (fees, min sizes, leverage) drift — code should read
  them from APIs where possible and docs mark researched values with dates.
- YOLO mode (`yolo.py`) is a LOUD, user-requested exception: the Phoenix test
  program grants non-withdrawable monthly credits, so it runs high leverage
  where liquidation is an expected learning outcome. It bypasses venture
  sizing/kill-switch by design but keeps: advisor-only, isolated margin,
  refuse-below-minimum, liquid markets only, own ledger sleeve ("yolo") so
  venture stats stay clean. Do not extend its exceptions to the real sleeves.
