"""The figures in docs/reviews/2026-11-13-short-workflows-measurement.md,
re-derived from the committed traces. Free: it reads files and calls nothing.

    python docs/probes/short_workflows_analysis.py \
        docs/traces/20261113T091013Z-short-workflows

The argument is the traces' common prefix. It reads PREFIX-shard-N.jsonl, the
runner's one line per unit, and PREFIX-phases-shard-N.jsonl, each shard's
database exported a row per line, which is where a quote's words are kept.
The scorer column is the tier-2 screen, never the result (D50); the hand
reading is in the report, not here.
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from collections import Counter, defaultdict

PREFIX = sys.argv[1]
SHAPES = ("SANITY", "LOOKUP", "DERIVATION", "SPECIFICATION", "PROCEDURE")
WORKFLOWS = ("answer-and-recompute", "verify-first")

units = [json.loads(line)
         for path in sorted(glob.glob(f"{PREFIX}-shard-*.jsonl"))
         for line in open(path, encoding="utf-8")]
ran = [u for u in units if not u.get("skipped")]


def passed(unit: dict) -> bool:
    return (unit.get("scorer") or {}).get("verdict") == "PASS"


def share(part: int, whole: int) -> str:
    return f"{part}/{whole} ({100 * part / whole:.0f}%)" if whole else "0/0"


def vote(unit: dict) -> dict:
    return unit.get("recompute_vote") or {}


spend = sum((u.get("cost") or 0) + (u.get("liability") or 0) for u in ran)
print(f"units {len(units)} | ran {len(ran)} | spend ${spend:.4f}")

for workflow in WORKFLOWS:
    mine = [u for u in ran if u["workflow"] == workflow]
    delivered = [u for u in mine if u.get("delivered")]
    costs = [u.get("cost") or 0 for u in mine]
    seconds = [u["seconds"] for u in mine]
    print(f"\n== {workflow}: delivered {share(len(delivered), len(mine))}"
          f" | scorer PASS {share(sum(map(passed, delivered)), len(mine))}"
          f" | status {dict(Counter(u['status'] for u in mine))}")
    print(f"   cost total ${sum(costs):.4f} mean ${statistics.mean(costs):.4f}"
          f" median ${statistics.median(costs):.4f} max ${max(costs):.4f}"
          f" | seconds mean {statistics.mean(seconds):.0f}"
          f" median {statistics.median(seconds):.0f} max {max(seconds):.0f}")
    for shape in SHAPES:
        these = [u for u in mine if u["shape"] == shape]
        print(f"   {shape:13} delivered"
              f" {share(sum(bool(u.get('delivered')) for u in these), len(these))}"
              f" scorer PASS {share(sum(passed(u) for u in these if u.get('delivered')), len(these))}")

print("\n== per question, scorer PASS of 3: answer-and-recompute | verify-first")
by_question: dict = defaultdict(lambda: defaultdict(list))
for unit in ran:
    by_question[unit["question"]][unit["workflow"]].append(unit)
for qid in sorted(by_question, key=lambda q: int(q[1:])):
    a, v = (by_question[qid][w] for w in WORKFLOWS)
    print(f"   {qid:4} {a[0]['shape']:13} {sum(map(passed, a))}/{len(a)}"
          f" | {sum(map(passed, v))}/{len(v)}")

answered = [u for u in ran
            if u["workflow"] == WORKFLOWS[0] and u.get("delivered")]
print("\n== the vote, answer-and-recompute")
for label, shapes in (("SANITY+DERIVATION", ("SANITY", "DERIVATION")),
                      ("all shapes", SHAPES)):
    these = [u for u in answered if u["shape"] in shapes]
    good = [u for u in these if passed(u)]
    bad = [u for u in these if not passed(u)]
    print(f"   {label}: unchecked {share(sum(not vote(u).get('checked') for u in these), len(these))}"
          f" | flagged, scorer PASS {share(sum(bool(vote(u).get('flagged')) for u in good), len(good))}"
          f" | flagged, scorer FAIL {share(sum(bool(vote(u).get('flagged')) for u in bad), len(bad))}"
          f" | with a not-comparable ask {sum(bool(vote(u).get('not_comparable')) for u in these)}")
print("   every flag, the answer's value against the samples' majority:")
for unit in answered:
    for d in vote(unit).get("disagreements") or [] if vote(unit).get("flagged") else []:
        print(f"     {unit['question']:4} r{unit['repeat']} ask {d['ask']}:"
              f" {d['answer']!r} | majority {d['majority']!r} ({d['support']} of 3)")

print("\n== switches")
asked = [(u, d) for u in ran for d in u.get("decisions") or []]
for name in ("needs_sources", "hard_request", "ask_covered", "quote_answers",
             "chunk_helps", "finding_answers"):
    these = [(u, d) for u, d in asked if d["switch"] == name]
    if not these:
        print(f"   {name}: not asked")
        continue
    print(f"   {name}: asked {len(these)}"
          f" | choice {dict(Counter(d['choice'] for _, d in these))}"
          f" | route {dict(Counter(d['route'] for _, d in these))}")
    if name in ("needs_sources", "hard_request"):
        for shape in SHAPES:
            print(f"      {shape:13}"
                  f" {dict(Counter(d['choice'] for u, d in these if u['shape'] == shape))}")
    else:
        p = [d["probability"] for _, d in these if d["probability"] is not None]
        print(f"      at 0.8 or above {share(sum(x >= 0.8 for x in p), len(p))}"
              f" | at 0.2 or below {sum(x <= 0.2 for x in p)}")

print("\n== grounding lookups, units with one, by shape")
for shape in SHAPES:
    these = [u for u in ran if u["shape"] == shape]
    print(f"   {shape:13} {share(sum(bool(u.get('lookups')) for u in these), len(these))}"
          f" | triage risk {dict(Counter(u.get('triage_risk') for u in these))}")


def quotes_in(node):
    if isinstance(node, dict):
        if isinstance(node.get("quotes"), list):
            yield from (q for q in node["quotes"] if isinstance(q, dict))
        for value in node.values():
            yield from quotes_in(value)
    elif isinstance(node, list):
        for value in node:
            yield from quotes_in(value)


print("\n== quote_answers, each answer beside the quote it judged")
for path in sorted(glob.glob(f"{PREFIX}-phases-shard-*.jsonl")):
    # Workflow ids restart at 1 in every shard: join within one file only.
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    phases = [r for r in rows if r["kind"] == "phase"]
    for phase in phases:
        if phase["phase"] != "answer_switches":
            continue
        judged = [r for r in phase["verdict"].get("records") or []
                  if r["switch"] == "quote_answers"]
        found = [q for p in phases
                 if p["workflow_id"] == phase["workflow_id"] and p["phase"] == "sources"
                 for q in quotes_in(p["verdict"]) if q.get("status") == "found"]
        for record, quote in zip(judged, found):
            same = quote.get("url") == record["item"]
            print(f"   [{record['choice']} {record['probability']:.3f}]"
                  f"{'' if same else ' (address differs: unpaired)'}")
            print(f"      question: {(quote.get('question_text') or '')[:150]}")
            print(f"      passage:  {(quote.get('text') or '')[:150]}")
