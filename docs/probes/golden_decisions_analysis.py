"""The figures in docs/reviews/2026-11-13-golden-decisions.md, re-derived from
the committed traces. Free: it reads files and calls nothing.

    python docs/probes/golden_decisions_analysis.py \
        docs/traces/20261113T180026Z-golden-batch1 \
        docs/traces/20261113T181530Z-same-meaning-replay.json

The first argument is batch 1's common prefix: PREFIX-shard-N.jsonl holds the
runner's one line per unit, PREFIX-phases-shard-N.jsonl each shard's database
exported a row per line. The second is the same-meaning replay's output. The
screens are never the result (D50); the hand reading is in the report.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter

PREFIX, REPLAY = sys.argv[1], sys.argv[2]
SWITCH_EVIDENCE_CHARS = 6000   # MAX_EVIDENCE_CHARS in autornd/routing/switches.py

units = [json.loads(line)
         for path in sorted(glob.glob(f"{PREFIX}-shard-*.jsonl"))
         for line in open(path, encoding="utf-8")]
units.sort(key=lambda u: (u["question"], u["repeat"]))
spend = sum((u.get("cost") or 0) + (u.get("liability") or 0) for u in units)
print(f"units {len(units)} | delivered {sum(bool(u.get('delivered')) for u in units)}"
      f" | spend ${spend:.4f}")

print("\n== each unit: cost, seconds, the screens' failed items, the vote")
for u in units:
    screen = u.get("scorer") or {}
    golden = [k for k, v in (screen.get("golden") or {}).items() if not v]
    tier2 = screen.get("tier2")
    t2 = "" if tier2 is None else (
        f" | tier-2 {tier2['verdict']}"
        + "".join(f" [{i['item']}]" for i in tier2["items"] if not i["pass"]))
    vote = u.get("recompute_vote") or {}
    why = ("checked" if vote.get("checked") else
           f"unchecked: {vote.get('samples_parsed')} sample(s) parsed" if (vote.get("samples_parsed") or 0) < 2 else
           f"unchecked: no consensus on asks {vote.get('no_consensus')}" if vote.get("no_consensus") else
           "unchecked: no value or verdict ask in the answer's results")
    print(f"   {u['question']:3} r{u['repeat']} ${u['cost']:.4f} {u['seconds']:5.0f}s"
          f" | golden {'holds' if not golden else 'fails ' + ','.join(golden)}{t2}"
          f" | vote {why}, flagged {vote.get('flagged')}"
          f" | answer {len(u.get('answer') or '')} chars")

print("\n== spend by question")
for qid in sorted({u["question"] for u in units}):
    print(f"   {qid:3} ${sum(u['cost'] for u in units if u['question'] == qid):.4f}")

asked = [(u, d) for u in units for d in u.get("decisions") or []]
print("\n== needs_sources, by question")
for qid in sorted({u["question"] for u in units}):
    print(f"   {qid:3} {dict(Counter(d['choice'] for u, d in asked if u['question'] == qid and d['switch'] == 'needs_sources'))}"
          f" | lookups ran in {sum(bool(u.get('lookups')) for u in units if u['question'] == qid)} of 3")


def quotes_in(node):
    if isinstance(node, dict):
        if isinstance(node.get("quotes"), list):
            yield from (q for q in node["quotes"] if isinstance(q, dict))
        for value in node.values():
            yield from quotes_in(value)
    elif isinstance(node, list):
        for value in node:
            yield from quotes_in(value)


print("\n== per shard: the asks, ask_covered below yes, quote_answers beside its quote")
quote_choices: Counter = Counter()
for path in sorted(glob.glob(f"{PREFIX}-phases-shard-*.jsonl")):
    # Workflow ids restart at 1 in every shard: join within one file only.
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    phases = [r for r in rows if r["kind"] == "phase"]
    for wid in sorted({p["workflow_id"] for p in phases}):
        mine = [p for p in phases if p["workflow_id"] == wid]
        asks = next(p["verdict"].get("asks") or [] for p in mine if p["phase"] == "asks")
        summary = next(str(p["verdict"].get("summary") or "") for p in mine
                       if p["phase"] == "implement")
        print(f"   {path.rsplit('-', 1)[-1]} workflow {wid}: ask kinds"
              f" {[a.get('kind') for a in asks]} | answer {len(summary)} chars")
        switches = next((p for p in mine if p["phase"] == "answer_switches"), None)
        records = (switches or {}).get("verdict", {}).get("records") or []
        for r in records:
            if r["switch"] == "ask_covered" and r["choice"] != "yes":
                n = int(r["item"].split()[-1])
                print(f"      ask_covered {r['item']} {r['choice']} {r['probability']:.2f}:"
                      f" {asks[n - 1]['quote'][:90]!r}")
        judged = [r for r in records if r["switch"] == "quote_answers"]
        found = [q for p in mine if p["phase"] == "sources"
                 for q in quotes_in(p["verdict"]) if q.get("status") == "found"]
        for record, quote in zip(judged, found):
            quote_choices[record["choice"]] += 1
            same = quote.get("url") == record["item"]
            print(f"      quote_answers [{record['choice']} {record['probability']:.3f}]"
                  f"{'' if same else ' (address differs: unpaired)'}")
            print(f"         question: {(quote.get('question_text') or '')[:140]}")
            print(f"         passage:  {(quote.get('text') or '')[:140]}")
print(f"   quote_answers choices {dict(quote_choices)}")

replay = json.load(open(REPLAY, encoding="utf-8"))
print(f"\n== same-meaning replay: {len(replay['pairs'])} pairs, ${replay['cost']:.5f}")
for kind in ("real", "contrary"):
    these = [p for p in replay["pairs"] if p["kind"] == kind]
    print(f"   {kind}: {dict(Counter(p['choice'] for p in these))}"
          f" | lowest {min(p['probability'] for p in these):.3f}"
          f" highest {max(p['probability'] for p in these):.3f}")
    for p in these:
        print(f"      {p['choice']:6} {p['probability']:.3f} {p['answer_value']!r} / {p['sample_value']!r}")
