"""Command-line interface. Run `two-sleeve --help` (or `python -m two_sleeve`).

Commands:
  scan      Market overview: funding board + trend state of the majors.
  plan      The advisor: what to do TODAY in both sleeves, in UI-click terms.
  report    Your ledger: PnL, win rate, sleeve budgets.
  log       Journal a trade open/close (paper or real).
  explain   Mini-lessons: funding, carry, sizing, liquidation, fees.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .carry import build_plan, evaluate_candidates
from .config import load_config
from .hyperliquid import HyperliquidPublic
from .ledger import Ledger, TradeClose, TradeOpen
from .lessons import LESSONS
from .sentiment import fear_greed
from .venture import scan_breakouts, scan_funding_fades


def _client() -> HyperliquidPublic:
    return HyperliquidPublic()


def cmd_scan(args: argparse.Namespace) -> int:
    cfg = load_config()
    client = _client()
    fng = fear_greed()
    if fng:
        value, label = fng
        print(f"Fear & Greed: {value}/100 ({label}) — regime dial, not a signal\n")
    print("== Funding board (carry universe) ==")
    print(f"{'coin':<6} {'mark':>12} {'fund now':>9} {'30d real':>9} "
          f"{'net APR':>8} {'neg hrs':>8}  status")
    for c in evaluate_candidates(client, cfg):
        status = "OK" if c.disqualified is None else c.disqualified
        print(f"{c.coin:<6} {c.mark_price:>12,.2f} {c.current_apr:>8.1%} "
              f"{c.realized_apr_30d:>8.1%} {c.net_apr:>8.1%} "
              f"{c.pct_hours_negative:>7.0%}  {status}")
    print("\n'fund now' = this hour's funding annualized; '30d real' = what "
          "shorts actually earned over 30 days; 'net APR' = blended estimate "
          "minus fees. Trust the 30d column.")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    cfg = load_config()
    client = _client()
    led = Ledger()

    print(f"two-sleeve v{__version__} — total equity ${cfg.total_equity_usd:,.2f} "
          f"(carry ${cfg.carry_equity:,.2f} / venture ${cfg.venture_equity:,.2f})\n")

    # ---- Sleeve 1
    print("== SLEEVE 1: carry (80%) ==")
    candidates = evaluate_candidates(client, cfg)
    plan = build_plan(candidates, cfg)
    if plan.action == "enter":
        print(f"ACTION: enter {plan.coin} carry")
        print(f"  1. On Hyperliquid SPOT: buy ${plan.spot_notional_usd:.2f} of {plan.coin}")
        print(f"  2. On Hyperliquid PERPS: with ${plan.perp_margin_usd:.2f} USDC margin, "
              f"SHORT ${plan.perp_short_notional_usd:.2f} of {plan.coin}-PERP "
              f"({plan.perp_leverage}x, isolated margin)")
        print(f"  3. Estimated liquidation on the short: ~{plan.est_liquidation_price:,.2f} "
              f"(price must rise that far against you)")
        print(f"  Expected: ~{plan.expected_net_apr:.1%} net APR "
              f"≈ ${plan.expected_monthly_usd:.2f}/month at this size")
    else:
        print(f"ACTION: {plan.action.replace('_', ' ')}")
    for n in plan.notes:
        print(f"  - {n}")

    # ---- Sleeve 2
    print("\n== SLEEVE 2: venture (20%) ==")
    open_venture = [t for t in led.open_trades() if t["sleeve"] == "venture"]
    ideas = scan_breakouts(client, cfg) + scan_funding_fades(client, cfg)
    if len(open_venture) >= cfg.venture.max_open_trades:
        print(f"ACTION: none — already at max {cfg.venture.max_open_trades} open trades. "
              "Manage what you have.")
    elif not ideas:
        print("ACTION: none. No fresh signals today — no trade IS the default "
              "state of this sleeve. Doing nothing is a position.")
    else:
        for i, idea in enumerate(ideas, 1):
            t = idea.trade
            print(f"IDEA {i}: {idea.signal} {t.symbol}")
            print(f"  entry ~{t.entry:g}, stop {t.stop:g}, "
                  f"size ${t.notional_usd:.2f} ({t.leverage}x), "
                  f"risk ${t.risk_usd:.2f}")
            print(f"  why: {idea.trigger_detail}")
        print("  If you take one: journal it first — "
              "`two-sleeve log open --sleeve venture ...`")

    if open_venture:
        print("\nOpen venture trades to manage (trail stops, honor them):")
        for t in open_venture:
            print(f"  {t['symbol']} {t['side']} ${t['notional_usd']:.2f} "
                  f"entry {t['entry']:g} stop {t.get('stop')}  ({t['ts']})")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    cfg = load_config()
    led = Ledger()
    for sleeve in ("carry", "venture"):
        s = led.summary(sleeve)
        print(f"== {sleeve} ==")
        for k, v in s.items():
            print(f"  {k}: {v}")
    total = led.summary()
    print(f"== total ==\n  net PnL: ${total['net_pnl_usd']}")
    budget = cfg.venture_equity
    vent = led.summary("venture")["net_pnl_usd"]
    if vent < 0 and abs(vent) >= budget:
        print(f"\n!! Venture sleeve has spent its ${budget:.2f} budget "
              f"(net {vent}). STOP opening venture trades until next deposit.")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    led = Ledger()
    if args.log_action == "open":
        rec = TradeOpen(sleeve=args.sleeve, symbol=args.symbol, side=args.side,
                        notional_usd=args.notional, entry=args.entry,
                        stop=args.stop, thesis=args.thesis,
                        paper=not args.real)
        led.append(rec)
        print(f"journaled open {rec.id}: {rec.sleeve} {rec.side} {rec.symbol} "
              f"${rec.notional_usd:.2f} @ {rec.entry:g}"
              + (" [REAL]" if args.real else " [paper]"))
    else:
        opens = {t["id"]: t for t in led.open_trades()}
        if args.ref not in opens:
            print(f"error: no open trade with id {args.ref}. Open trades: "
                  f"{list(opens) or 'none'}", file=sys.stderr)
            return 1
        rec = TradeClose(ref=args.ref, exit=args.exit, pnl_usd=args.pnl,
                         fees_usd=args.fees, lesson=args.lesson)
        led.append(rec)
        print(f"journaled close of {args.ref}: pnl ${args.pnl:.2f}, "
              f"fees ${args.fees:.2f}")
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    topic = args.topic
    if topic not in LESSONS:
        print(f"topics: {', '.join(sorted(LESSONS))}")
        return 0 if topic is None else 1
    print(LESSONS[topic])
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="two-sleeve", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="funding board + market state").set_defaults(fn=cmd_scan)
    sub.add_parser("plan", help="today's advisor output for both sleeves").set_defaults(fn=cmd_plan)
    sub.add_parser("report", help="ledger PnL and sleeve budgets").set_defaults(fn=cmd_report)

    lg = sub.add_parser("log", help="journal a trade")
    lg_sub = lg.add_subparsers(dest="log_action", required=True)
    lo = lg_sub.add_parser("open")
    lo.add_argument("--sleeve", choices=["carry", "venture"], required=True)
    lo.add_argument("--symbol", required=True)
    lo.add_argument("--side", choices=["long", "short", "carry"], required=True)
    lo.add_argument("--notional", type=float, required=True)
    lo.add_argument("--entry", type=float, required=True)
    lo.add_argument("--stop", type=float, default=None)
    lo.add_argument("--thesis", required=True,
                    help="why you're taking the trade — required on purpose")
    lo.add_argument("--real", action="store_true",
                    help="mark as a real-money trade (default: paper)")
    lo.set_defaults(fn=cmd_log)
    lc = lg_sub.add_parser("close")
    lc.add_argument("--ref", required=True, help="id printed at open")
    lc.add_argument("--exit", type=float, required=True)
    lc.add_argument("--pnl", type=float, required=True)
    lc.add_argument("--fees", type=float, default=0.0)
    lc.add_argument("--lesson", required=True,
                    help="what you learned — required, even on winners")
    lc.set_defaults(fn=cmd_log)

    ex = sub.add_parser("explain", help="mini-lessons")
    ex.add_argument("topic", nargs="?", default=None)
    ex.set_defaults(fn=cmd_explain)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except ConnectionError as e:
        print(f"network error talking to Hyperliquid: {e}\n"
              "(Are you offline, or behind a proxy that blocks api.hyperliquid.xyz?)",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
