"""The figures in docs/reviews/2026-11-13-lookup-quotes.md, re-derived from
the committed traces. Free: it reads files and calls nothing.

    python docs/probes/lookup_quotes_analysis.py \
        docs/traces/20261113T225626Z-lookup-runA \
        docs/traces/20261113T225626Z-lookup-runB

Each argument is one run's common prefix: PREFIX-shard-N.jsonl holds the
runner's one line per unit, PREFIX-phases-shard-N.jsonl each shard's database
exported a row per line. The confident no's of the two earlier runs the
preregistration counts (docs/preregistration-20261113-lookup-quotes.md, item
1) are listed from their own traces, EARLIER. The screens are never the
result (D50); the hand reading is in the report.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
# config.py exits at import without the six tiers, and pydantic reads the
# .env in the working directory: placeholders through the environment, as
# tests/conftest.py does. Nothing here calls a model.
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION",
             "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"

from autornd.graph.checks import answer_ends_whole  # noqa: E402

PREFIXES = sys.argv[1:]
EARLIER = ("docs/traces/20261113T091013Z-short-workflows",
           "docs/traces/20261113T180026Z-golden-batch1")
CONFIDENT_NO = 0.20     # the preregistration's bar: a probability of 0.20 or less


def quotes_in(node):
    if isinstance(node, dict):
        if isinstance(node.get("quotes"), list):
            yield from (q for q in node["quotes"] if isinstance(q, dict))
        for value in node.values():
            yield from quotes_in(value)
    elif isinstance(node, list):
        for value in node:
            yield from quotes_in(value)


def shards(prefix: str):
    """Each shard's phase rows and workflow rows. Workflow ids restart at 1
    in every shard, so every join stays inside one file."""
    for path in sorted(glob.glob(f"{prefix}-phases-shard-*.jsonl")):
        rows = [json.loads(line) for line in open(path, encoding="utf-8")]
        yield (path.rsplit("-", 1)[-1].removesuffix(".jsonl"),
               [r for r in rows if r["kind"] == "phase"],
               {r["id"]: r for r in rows if r["kind"] == "workflow"})


def judged_quotes(prefix: str):
    """Every quote_answers record beside the found quote it was asked about.
    The switch's items are the found quotes in the order the sources phases
    stored them (_quote_items in autornd/graph/adapter.py), so the pairing
    is by order and checked by address."""
    for shard, phases, _ in shards(prefix):
        for wid in sorted({p["workflow_id"] for p in phases}):
            mine = [p for p in phases if p["workflow_id"] == wid]
            records = [r for p in mine if p["phase"] == "answer_switches"
                       for r in p["verdict"].get("records") or []
                       if r["switch"] == "quote_answers"]
            found = [q for p in mine if p["phase"] == "sources"
                     for q in quotes_in(p["verdict"]) if q.get("status") == "found"]
            for record, quote in zip(records, found):
                yield shard, wid, record, quote, quote.get("url") == record["item"]


for prefix in PREFIXES:
    units = [json.loads(line)
             for path in sorted(glob.glob(f"{prefix}-shard-*.jsonl"))
             for line in open(path, encoding="utf-8")]
    units.sort(key=lambda u: (u["question"], u["repeat"]))
    spend = sum((u.get("cost") or 0) + (u.get("liability") or 0) for u in units)
    print(f"\n######## {prefix}")
    print(f"units {len(units)} | delivered {sum(bool(u.get('delivered')) for u in units)}"
          f" | statuses {dict(Counter(u['status'] for u in units))} | spend ${spend:.4f}"
          f" | seconds {min(u['seconds'] for u in units):.0f}-{max(u['seconds'] for u in units):.0f}")

    print("\n== each unit: status, cost, the cut-off check on its text, the screens, the vote")
    for u in units:
        text = u.get("answer") or u.get("candidate") or ""
        end = answer_ends_whole(text)
        screen = u.get("scorer") or {}
        golden = [k for k, v in (screen.get("golden") or {}).items() if not v]
        tier2 = screen.get("tier2") if "tier2" in screen else (
            screen if screen.get("items") else None)
        t2 = "" if tier2 is None else (
            f" | tier-2 {tier2['verdict']}"
            + "".join(f" [{i['item']}]" for i in tier2["items"] if not i["pass"]))
        g = "" if "golden" not in screen else (
            f" | golden {'holds' if not golden else 'fails ' + ','.join(golden)}")
        vote = u.get("recompute_vote") or {}
        print(f"   {u['question']:3} r{u['repeat']} {u['status']:9}"
              f" ${u['cost']:.4f}+{u.get('liability') or 0:.4f} {u['seconds']:4.0f}s"
              f" | {len(text)} chars, {'ends whole' if end.passed else 'CUT: ' + ', '.join(end.data['signs'])}"
              f"{g}{t2}"
              f" | vote checked {vote.get('checked')} flagged {vote.get('flagged')}"
              f" text disagreements {sum(isinstance(d.get('answer'), str) for d in vote.get('disagreements') or [])}"
              f"{' | error ' + str(u['error'])[:90] if u.get('error') else ''}")

    print("\n== spend by question")
    for qid in sorted({u["question"] for u in units}):
        these = [u for u in units if u["question"] == qid]
        print(f"   {qid:3} ${sum(u['cost'] for u in these):.4f} over {len(these)}"
              f" (${sum(u['cost'] for u in these) / len(these):.4f} each)")

    asked = [(u, d) for u in units for d in u.get("decisions") or []]
    print("\n== needs_sources and the lookups, by question")
    for qid in sorted({u["question"] for u in units}):
        these = [u for u in units if u["question"] == qid]
        statuses = Counter(s for u in these for lookup in u.get("lookups") or []
                           for s in lookup.get("quotes") or [])
        print(f"   {qid:3} {dict(Counter(d['choice'] for u, d in asked if u['question'] == qid and d['switch'] == 'needs_sources'))}"
              f" | lookups ran in {sum(bool(u.get('lookups')) for u in these)} of {len(these)}"
              f" | quote statuses {dict(statuses)}")

    print("\n== every decision switch, by choice")
    for name in sorted({d["switch"] for u, d in asked}):
        mine = [d for u, d in asked if d["switch"] == name]
        print(f"   {name:14} {dict(Counter(d['choice'] for d in mine))}")

    print("\n== ask_covered below yes")
    for shard, phases, _ in shards(prefix):
        for p in phases:
            if p["phase"] != "answer_switches":
                continue
            asks = next((q["verdict"].get("asks") or [] for q in phases
                         if q["workflow_id"] == p["workflow_id"] and q["phase"] == "asks"), [])
            for r in p["verdict"].get("records") or []:
                if r["switch"] == "ask_covered" and r["choice"] != "yes":
                    n = int(r["item"].split()[-1])
                    quote = asks[n - 1]["quote"] if 0 < n <= len(asks) else "?"
                    print(f"   {shard} workflow {p['workflow_id']} {r['item']} {r['choice']}"
                          f" {r['probability']:.2f}: {quote[:100]!r}")

    print("\n== same_meaning, each question beside the disagreement it was asked about")
    for shard, phases, _ in shards(prefix):
        for p in phases:
            if p["phase"] != "answer_switches":
                continue
            vote = next((q["verdict"] for q in phases if q["workflow_id"] == p["workflow_id"]
                         and q["phase"] == "recompute_vote"), {})
            text = {f"ask {d['ask']}": d for d in vote.get("disagreements") or []
                    if isinstance(d.get("answer"), str)}
            for r in p["verdict"].get("records") or []:
                if r["switch"] == "same_meaning":
                    d = text.get(r["item"], {})
                    print(f"   {shard} workflow {p['workflow_id']} {r['item']}"
                          f" [{r['choice']} {r['probability']:.3f}]"
                          f" answer {str(d.get('answer'))[:80]!r} / samples {str(d.get('majority'))[:60]!r}")

    print("\n== quote_answers, each answer beside the quote it judged")
    choices: Counter = Counter()
    for shard, wid, record, quote, same in judged_quotes(prefix):
        choices[record["choice"]] += 1
        confident = " CONFIDENT NO" if record["probability"] <= CONFIDENT_NO else ""
        print(f"   {shard} workflow {wid} [{record['choice']} {record['probability']:.3f}]{confident}"
              f"{'' if same else ' (address differs: unpaired)'}")
        print(f"      question: {(quote.get('question_text') or '')[:200]}")
        print(f"      passage:  {(quote.get('text') or '')[:300]!r}")
    print(f"   choices {dict(choices)}")

print("\n######## quote_answers confident no's, the preregistration's item 1")
total = 0
for prefix in (*EARLIER, *PREFIXES):
    nos = [(shard, wid, record) for shard, wid, record, quote, same in judged_quotes(prefix)
           if same and record["probability"] <= CONFIDENT_NO]
    total += len(nos)
    print(f"   {prefix}: {len(nos)}"
          + "".join(f"\n      {s} workflow {w} {r['probability']:.3f}" for s, w, r in nos))
print(f"   in all: {total}")
