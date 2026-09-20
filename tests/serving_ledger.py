"""Derive the serving ledger from the committed traces.

**Why this exists.** Which serving works at which tier is the most expensive
fact this project keeps re-buying. It was recorded in §6.1's table, §6.11's
convergence finding, B4's six-way pin test, the B12 sweep traces and two
pre-registrations — and in none of them together, so every session re-derived
it from trace headers at the cost of a live run. §6.1 even carries a row
reading "(unrecorded, likely StreamLake)".

Convention 24 says a fact about the repo is generated or guarded, never
hand-stamped. This derives it: every committed trace header names its model map
and its provider pins, and every unit beneath it names an outcome. The ledger is
that join, and `tests/test_serving_ledger.py` regenerates it and fails if the
committed table has drifted.

**What it is not.** A ranking. Unit counts here are whatever the blueprints
happened to run, not a designed comparison — an arm with 200 units and one with
3 are not comparable, and the table says so in its own n column. Convention 23
still applies: compliance first, then iterations, then speed, never at n=1.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path


def derive(traces_dir: str | Path) -> dict[tuple[str, str, str], collections.Counter]:
    """(tier, model, provider) -> Counter of terminal statuses, from the traces."""
    combos: dict[tuple[str, str, str], collections.Counter] = collections.defaultdict(
        collections.Counter)
    for path in sorted(Path(traces_dir).glob("*.jsonl")):
        header = None
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("record") == "header":
                header = rec
            elif rec.get("record") == "unit" and header:
                models = header.get("models", {})
                order = header.get("provider_order") or ""
                pins = dict(
                    p.split(":", 1) for p in order.split(",") if ":" in p)
                status = rec.get("status") or "error"
                for tier, provider in pins.items():
                    if not provider:          # explicitly unpinned — not a pin
                        continue
                    combos[(tier, models.get(tier, "?"), provider)][status] += 1
    return combos


def render(combos) -> str:
    """The committed table. Sorted so the output is stable across runs."""
    lines = ["| tier | model | serving | n | completed | other terminals | errors |",
             "|---|---|---|---|---|---|---|"]
    for key in sorted(combos):
        tier, model, provider = key
        c = combos[key]
        total = sum(c.values())
        done = c.get("completed", 0)
        errs = c.get("error", 0)
        other = total - done - errs
        other_s = ", ".join(
            f"{k} {v}" for k, v in sorted(c.items())
            if k not in ("completed", "error")) or "—"
        lines.append(
            f"| `{tier}` | `{model}` | **{provider}** | {total} | {done} | {other_s} | {errs} |")
    return "\n".join(lines)
