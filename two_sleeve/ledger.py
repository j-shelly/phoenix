"""A dead-simple trade journal, stored as JSON lines in
~/.two-sleeve/ledger.jsonl (see paths.py for the TWO_SLEEVE_DATA_DIR override).

Every trade — paper or real, carry or venture — gets journaled here. The
single highest-leverage habit in trading is writing down why you entered
BEFORE you enter, and grading the trade after. The `report` command reads
this file to show your PnL, win rate, and whether sleeve 2 is staying inside
its loss budget.

Records are append-only: closing a trade appends a "close" record referencing
the open record's id. Nothing is ever rewritten, so the file is also your
audit trail.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .paths import DATA_DIR

DEFAULT_LEDGER = DATA_DIR / "ledger.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class TradeOpen:
    sleeve: str               # "carry" or "venture"
    symbol: str
    side: str                 # "long" | "short" | "carry" (spot+perp pair)
    notional_usd: float
    entry: float
    stop: float | None
    thesis: str               # WHY — required. "number went up" is not a thesis.
    paper: bool = True
    record: str = "open"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: str = field(default_factory=_now_iso)


@dataclass
class TradeClose:
    ref: str                  # id of the open record
    exit: float
    pnl_usd: float
    fees_usd: float
    lesson: str               # what you learned — required, even on winners
    record: str = "close"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: str = field(default_factory=_now_iso)


class Ledger:
    def __init__(self, path: Path = DEFAULT_LEDGER):
        self.path = path

    def append(self, rec: TradeOpen | TradeClose) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # If a previous write was cut off mid-line (no trailing newline), a
        # plain append would glue this record onto the broken line and corrupt
        # it too. Start a fresh line so the damage stays contained.
        needs_newline = False
        if self.path.exists() and self.path.stat().st_size > 0:
            with self.path.open("rb") as f:
                f.seek(-1, 2)
                needs_newline = f.read(1) != b"\n"
        with self.path.open("a", encoding="utf-8") as f:
            if needs_newline:
                f.write("\n")
            f.write(json.dumps(asdict(rec)) + "\n")

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    # A truncated append must not brick the whole journal.
                    print(f"warning: skipping malformed ledger line "
                          f"{self.path}:{lineno} (truncated write? inspect it)",
                          file=sys.stderr)
        return out

    def open_trades(self) -> list[dict]:
        """Open records with no matching close record."""
        recs = self.records()
        closed = {r["ref"] for r in recs if r.get("record") == "close"}
        return [r for r in recs if r.get("record") == "open" and r["id"] not in closed]

    def closed_trades(self) -> list[tuple[dict, dict]]:
        """(open, close) pairs, in close order."""
        recs = self.records()
        opens = {r["id"]: r for r in recs if r.get("record") == "open"}
        out = []
        for r in recs:
            if r.get("record") == "close" and r["ref"] in opens:
                out.append((opens[r["ref"]], r))
        return out

    def summary(self, sleeve: str | None = None, paper: bool | None = None,
                month: str | None = None) -> dict:
        """Aggregate stats. Filters: `sleeve` ("carry"/"venture"), `paper`
        (True = paper only, False = real-money only, None = both), `month`
        ("YYYY-MM", matched against the CLOSE timestamp).

        Paper and real must never be summed for risk decisions — a paper win
        can mask a real loss. The kill switch uses paper=False.
        """
        pairs = self.closed_trades()
        if sleeve:
            pairs = [(o, c) for o, c in pairs if o["sleeve"] == sleeve]
        if paper is not None:
            pairs = [(o, c) for o, c in pairs if o.get("paper", True) == paper]
        if month:
            pairs = [(o, c) for o, c in pairs if c["ts"].startswith(month)]
        pnls = [c["pnl_usd"] - c.get("fees_usd", 0.0) for _, c in pairs]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        open_trades = [
            t for t in self.open_trades()
            if (sleeve is None or t["sleeve"] == sleeve)
            and (paper is None or t.get("paper", True) == paper)
        ]
        return {
            "trades": len(pnls),
            "net_pnl_usd": round(sum(pnls), 2),
            "win_rate": round(len(wins) / len(pnls), 3) if pnls else None,
            "avg_win_usd": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss_usd": round(sum(losses) / len(losses), 2) if losses else None,
            "open_trades": len(open_trades),
        }
