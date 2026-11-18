"""The acceptance run's figures, read off the records and the readers' verdicts. Free.

    python -I docs/probes/acceptance_run_analysis.py REPO CODES_JSON VERDICTS_GLOB [FINAL_JSON]

Run from the repository root, with the run's directories under evals/results/
(or copied there from docs/traces/). CODES_JSON is the file blind_reading_packets.py
kept back from the readers; VERDICTS_GLOB matches the blind readers' files.
FINAL_JSON, when given, is code -> {"verdict": ...}: the executor's second reading,
which overrides the blind reader where the two differ.

For each delivered answer it joins the verdict to the delivery's cautions (as
recorded by the runner, built by `_detail`, the API's own builder) and to the
confirmation, rebuilt from the stored phase rows with this tree's code, since
the runner does not record confirmations. A caution "points" when it names the
wrong part: two pages differ, or a figure is on none of the pages. "The vote
did not run" and "nothing was checked" say what was not done and point at
nothing. It prints the preregistered bars (docs/preregistration-20261117-acceptance-run.md).
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
CODES = json.loads(Path(sys.argv[2]).read_text())
sys.path.insert(0, str(REPO))
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION",
             "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"

from autornd.api import routes  # noqa: E402

verdicts: dict = {}
for path in sorted(glob.glob(sys.argv[3])):
    verdicts.update(json.loads(Path(path).read_text()))
final: dict = {}
if len(sys.argv) > 4:
    final = json.loads(Path(sys.argv[4]).read_text())

KEYS = {q["id"]: q for name in ("questions.json", "hard-questions.json",
                                "misleading-questions.json",
                                "holdout-questions.json")
        for q in json.loads((REPO / "evals/professional" / name).read_text())["questions"]}
SET_OF = {"P": "professional", "H": "hard", "M": "misleading", "X": "holdout"}


def group_of(question: str) -> str:
    """The hold-out set's three authoring groups (X1-14, X15-28, X29-42); the
    other sets are their own group. Bar 7 of the hold-out run reads by group."""
    if question[0] != "X":
        return SET_OF[question[0]]
    n = int(question[1:])
    return ("holdout EU and international" if n <= 14 else
            "holdout software and standards" if n <= 28 else
            "holdout physical engineering")
POINTING = ("give different figures for the same thing",
            "is in none of the passages found")

_lines: dict[str, list] = {}
_phases: dict[str, list] = {}


def unit(source: str) -> dict:
    path, n = source.rsplit("#", 1)
    if path not in _lines:
        _lines[path] = [json.loads(x) for x in open(REPO / path, encoding="utf-8")]
    return _lines[path][int(n)]


def delivery(source: str, question: str) -> tuple[list[int], list, list[str]]:
    """The delivery rebuilt from the stored rows exactly as `_detail` builds it:
    the asks the "figures stand in a found passage" line covers, the answer's
    figure for each ask, and the cautions. The cautions are compared with the
    ones the runner recorded, so a rebuild that does not match the shipped
    delivery stops the script instead of being reported."""
    path, n = source.rsplit("#", 1)
    phases_path = str(Path(path).parent / ("phases-" + Path(path).name))
    if phases_path not in _phases:
        _phases[phases_path] = [json.loads(x) for x in
                                open(REPO / phases_path, encoding="utf-8")]
    rows_ = _phases[phases_path]
    workflow = [r for r in rows_ if r["kind"] == "workflow"][int(n)]
    if KEYS[question]["question"][:40] not in workflow["request"]:
        raise SystemExit(f"{source}: workflow {workflow['id']} is not {question}")
    # `_detail` orders phases by created_at, not by row id.
    phases = sorted((r for r in rows_ if r["kind"] == "phase"
                     and r["workflow_id"] == workflow["id"]),
                    key=lambda r: r["created_at"])
    verdicts_ = [(r["phase"], json.loads(json.dumps(r["verdict"]))) for r in phases]
    answer = next((v.get("summary") for name, v in reversed(verdicts_)
                   if name == "implement" and isinstance(v, dict)), None)
    vote = next((v for name, v in reversed(verdicts_) if name == "recompute_vote"), None)
    sources = [v for name, v in verdicts_ if name == "sources"]
    vote = routes._settled(verdicts_, vote, sources)
    results = next((v.get("results") for name, v in reversed(verdicts_)
                    if name == "implement" and isinstance(v, dict)), None)
    differing = routes._differing(sources)
    backed, unconfirmed = routes._checked_figures(results, sources, differing)
    if vote is not None and backed:
        vote = dict(vote, backed_by_source=backed)
    asked = next((len(v.get("asks") or []) for name, v in reversed(verdicts_)
                  if name == "asks" and isinstance(v, dict)), 0)
    cautions = routes._cautions(vote, sources, answer is not None, asked,
                                unconfirmed, differing,
                                calculation=routes._judged_a_calculation(verdicts_))
    figures = [(r.get("ask"), r.get("value")) for r in results or []
               if isinstance(r, dict)]
    return (backed if routes._confirmations(backed, True) else []), figures, cautions


rows = []
for code, meta in CODES.items():
    if not meta["delivered"]:
        continue
    verdict = (final.get(code) or verdicts.get(code) or {}).get("verdict", "MISSING")
    u = unit(meta["source"])
    backed, figures, rebuilt = delivery(meta["source"], meta["question"])
    cautions = u.get("cautions") or []
    if rebuilt != cautions:
        raise SystemExit(f"{meta['source']}: the rebuilt cautions are not the shipped ones")
    rows.append({
        "code": code, "q": meta["question"], "set": group_of(meta["question"]),
        "verdict": verdict, "cautions": cautions,
        "points": any(p in c for c in cautions for p in POINTING),
        "confirmed": bool(backed), "backed": backed, "figures": figures,
        "cost": float(u.get("cost") or 0) + float(u.get("liability") or 0),
        "seconds": float(u.get("seconds") or 0), "source": meta["source"],
    })

n = len(rows)
HOLDOUT = all(r["q"][0] == "X" for r in rows)
# The bars of each run's preregistration. The hold-out's are in
# docs/preregistration-20261117-holdout-run.md; counts there are of ALL units
# made (126), not of those delivered, so a blocked answer is not a right one.
BARS = ({"right": "at least 100 of 126 made", "set": "70%"} if HOLDOUT else
        {"right": "at least 240 of 264", "set": "85%"})
right = [r for r in rows if r["verdict"] == "right"]
wrong = [r for r in rows if r["verdict"] != "right"]
print(f"answers read: {n}; missing verdicts: {sum(r['verdict'] == 'MISSING' for r in rows)}")
print(f"BAR 1  right: {len(right)} of {n} delivered   (bar: {BARS['right']})")
by_set: dict = defaultdict(Counter)
for r in rows:
    by_set[r["set"]]["n"] += 1
    by_set[r["set"]]["right"] += r["verdict"] == "right"
for s, c in by_set.items():
    print(f"BAR {'7' if HOLDOUT else '6'}  {s}: {c['right']} of {c['n']} = {100 * c['right'] / c['n']:.1f}%   (bar: {BARS['set']})")
print(f"BAR 2  not-right answers carrying a confirmation: "
      f"{sum(r['confirmed'] for r in wrong)} of {len(wrong)}; whether the ask a confirmation "
      f"covers is the wrong one is read off the listing below")
print(f"BAR 3  right answers with no caution: "
      f"{sum(not r['cautions'] for r in right)} of {len(right)}   (bar: at least half)")
print(f"BAR 4  wrong answers with a pointing caution: "
      f"{sum(r['points'] for r in wrong)} of {len(wrong)}   (bar: at least half)")
print(f"BAR 5  cost an answer: ${sum(r['cost'] for r in rows) / n:.4f}   (bar: at most $0.015); "
      f"total of the {n} answers ${sum(r['cost'] for r in rows):.2f}")
print(f"       seconds an answer: {sum(r['seconds'] for r in rows) / n:.0f}")
print(f"       answers carrying a confirmation: {sum(r['confirmed'] for r in rows)}; "
      f"with any caution: {sum(bool(r['cautions']) for r in rows)}; "
      f"with a pointing caution: {sum(r['points'] for r in rows)}")
print(f"       right answers carrying a pointing caution: {sum(r['points'] for r in right)}")
per_q: dict = defaultdict(Counter)
for r in rows:
    per_q[r["q"]]["n"] += 1
    per_q[r["q"]]["right"] += r["verdict"] == "right"
print("PER QUESTION (right of answered), those below 6 of 6:")
for q, c in sorted(per_q.items(), key=lambda kv: (kv[0][0], int(kv[0][1:]))):
    if c["right"] < c["n"]:
        print(f"  {q}: {c['right']} of {c['n']}")
print("EVERY ANSWER NOT RIGHT:")
for r in wrong:
    print(f"  {r['q']} {r['code']} {r['verdict']} confirmed={r['confirmed']} "
          f"points={r['points']} cautions={len(r['cautions'])} backed asks={r['backed']} "
          f"figures={str(r['figures'])[:90]} {r['source']}")
    for c in r["cautions"]:
        print("      caution:", c[:200])
