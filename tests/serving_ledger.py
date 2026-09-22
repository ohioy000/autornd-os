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

**The blind spot this used to have, and why it is the canonical Convention 28
exhibit.** The derivation walked the header's PINS and skipped any tier whose
pin was empty. So an unpinned tier produced no row — and the rendered table
carried three tiers while looking complete. The tier missing from it was
`escalation`, which §6.10 measures at **70–78% of hard-trace spend** and which a
single 2026-09-22 run showed taking **$0.1080 of $0.1547**. The most expensive
tier in the system was the one the instrument could not see, and nothing said
so: the table asserted a set of servings without asserting it had looked at
every tier.

It now enumerates every tier the traces mention and gives each an explicit
status — **measured**, **rotated** (served without a pin, which is still
evidence about a `(model, provider)` pair), or **unmeasured** with the reason.
A tier cannot be silently absent, and `tests/test_serving_ledger.py` fails if
one is.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path


def derive(traces_dir: str | Path):
    """Read every trace once and return (combos, tiers_seen).

    `combos` maps (tier, model, provider, pinned) to a Counter of terminal
    statuses. `pinned` is part of the key rather than a column computed later,
    because the same provider can serve a tier both ways and folding them would
    report a pin's evidence and rotation's evidence as one number.

    `tiers_seen` is every tier any header names a model for — the denominator
    that makes an absent row detectable. Derived rather than listed, so a tier
    added to the map tomorrow appears here without anyone remembering.
    """
    combos = collections.defaultdict(collections.Counter)
    tiers_seen: set[str] = set()
    for path in sorted(Path(traces_dir).glob("*.jsonl")):
        header = None
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("record") == "header":
                header = rec
                tiers_seen.update(header.get("models", {}))
            elif rec.get("record") == "unit" and header:
                models = header.get("models", {})
                order = header.get("provider_order") or ""
                pins = {t: p for t, p in
                        (e.split(":", 1) for e in order.split(",") if ":" in e)}
                status = rec.get("status") or "error"

                # Pinned arms, unchanged: the numbers already in the committed
                # table must not move, and a test asserts they do not.
                for tier, provider in pins.items():
                    if not provider:
                        continue
                    combos[(tier, models.get(tier, "?"), provider, True)][status] += 1

                # Rotated arms. Who actually answered is recorded per unit, and
                # it is evidence about a (model, provider) pair whether or not
                # anyone pinned it. Skipping these is what made escalation --
                # 70-78% of hard-trace spend -- invisible.
                served = rec.get("providers_by_function") or {}
                for tier, providers in served.items():
                    if pins.get(tier):
                        continue              # already counted as a pin
                    for provider in providers or []:
                        combos[(tier, models.get(tier, "?"), provider, False)][status] += 1
    return combos, tiers_seen


def render(combos, tiers_seen=()) -> str:
    """The committed table. Sorted so the output is stable across runs.

    Every tier in `tiers_seen` gets a row or an explicit unmeasured line. A
    table that silently omits a tier reads as complete, which is how the most
    expensive tier in the system stayed invisible.
    """
    lines = ["| tier | model | serving | how | n | completed | other terminals | errors |",
             "|---|---|---|---|---|---|---|---|"]
    for key in sorted(combos):
        tier, model, provider, pinned = key
        c = combos[key]
        total = sum(c.values())
        done = c.get("completed", 0)
        errs = c.get("error", 0)
        other_s = ", ".join(
            f"{k} {v}" for k, v in sorted(c.items())
            if k not in ("completed", "error")) or "—"
        how = "pinned" if pinned else "rotated"
        lines.append(
            f"| `{tier}` | `{model}` | **{provider}** | {how} | {total} | "
            f"{done} | {other_s} | {errs} |")

    measured = {key[0] for key in combos}
    absent = sorted(set(tiers_seen) - measured)
    if absent:
        lines.append("")
        lines.append(
            "**Unmeasured tiers:** " + ", ".join(f"`{t}`" for t in absent)
            + " — named in a trace header's model map, but no committed unit "
              "records a provider for them. They ran no calls, or ran them "
              "before per-tier attribution existed. Listed rather than omitted, "
              "because an absent row reads as a tier that does not exist.")
    return "\n".join(lines)
