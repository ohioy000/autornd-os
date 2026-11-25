"""The second hold-out run's figures, read off the records and the readers' verdicts. Free.

    python -I docs/probes/holdout2_analysis.py REPO CODES_JSON VERDICTS_GLOB [FINAL_JSON]

Adapted from acceptance_run_analysis.py (the delivery, cautions and confirmations are rebuilt the same
way, from the stored phase rows with this tree's code, and a rebuild that does not match the shipped
delivery stops the script). CODES_JSON is the file blind_reading_packets.py kept back from the readers;
VERDICTS_GLOB matches the blind readers' files; FINAL_JSON, when given, is code -> {"verdict": ...}: the
executor's reading, which overrides the blind reader where the two differ. It prints the bars of
docs/preregistration-20261122-holdout2-run.md: the arms are the directory the unit's shard sits in
(N1..N6 and O), groups are the set's blocks of 14 ids, and the comparison is N3..N6 against O.
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

KEYS = {q["id"]: q for q in json.loads(
    (REPO / "evals/professional/holdout2-questions.json").read_text())["questions"]}


def group_of(question: str) -> int:
    """The set's own groups: blocks of 14 ids, Y1-14 is group 1."""
    return (int(question[1:]) - 1) // 14 + 1


def arm_of(source: str) -> str:
    return Path(source.rsplit("#", 1)[0]).parent.name


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
made = {}
for code, meta in CODES.items():
    made[code] = meta
    if not meta["delivered"]:
        continue
    verdict = (final.get(code) or verdicts.get(code) or {}).get("verdict", "MISSING")
    u = unit(meta["source"])
    backed, figures, rebuilt = delivery(meta["source"], meta["question"])
    cautions = u.get("cautions") or []
    if rebuilt != cautions:
        raise SystemExit(f"{meta['source']}: the rebuilt cautions are not the shipped ones")
    rows.append({
        "code": code, "q": meta["question"], "arm": arm_of(meta["source"]),
        "group": group_of(meta["question"]),
        "verdict": verdict, "cautions": cautions,
        "points": any(p in c for c in cautions for p in POINTING),
        "confirmed": bool(backed), "backed": backed, "figures": figures,
        "cost": float(u.get("cost") or 0) + float(u.get("liability") or 0),
        "seconds": float(u.get("seconds") or 0), "source": meta["source"],
    })
# every unit made, delivered or not, for the counts of the bars (an answer blocked is not a right one)
all_units = [dict(m, code=c, arm=arm_of(m["source"]), group=group_of(m["question"]))
             for c, m in made.items()]
NEW_ARMS = ("N1", "N2", "N3", "N4", "N5", "N6")
new = [r for r in rows if r["arm"] in NEW_ARMS]
new_made = [m for m in all_units if m["arm"] in NEW_ARMS]
right = [r for r in new if r["verdict"] == "right"]
wrong = [r for r in new if r["verdict"] != "right"]
print(f"answers read: {len(rows)} of {len(all_units)} made; missing verdicts: {sum(r['verdict'] == 'MISSING' for r in rows)}")
print(f"BAR 1  right, N1-N6: {len(right)} of {len(new_made)} made ({len(new)} delivered)   (bar: at least 138 of 174)")
by_group: dict = defaultdict(Counter)
for m in new_made:
    by_group[m["group"]]["n"] += 1
for r in new:
    by_group[r["group"]]["right"] += r["verdict"] == "right"
for g in sorted(by_group):
    c = by_group[g]
    print(f"BAR 7  group {g}: {c['right']} of {c['n']} made = {100 * c['right'] / c['n']:.1f}%   (bar: at least 50%)")
print(f"BAR 2  not-right answers carrying a confirmation: "
      f"{sum(r['confirmed'] for r in wrong)} of {len(wrong)}; whether the ask a confirmation "
      f"covers is the wrong one is read off the listing below")
print(f"BAR 3  right answers with no caution: "
      f"{sum(not r['cautions'] for r in right)} of {len(right)}   (bar: at least half)")
print(f"BAR 4  wrong answers with a pointing caution: "
      f"{sum(r['points'] for r in wrong)} of {len(wrong)}   (bar: at least half)")
for arm in NEW_ARMS + ("O",):
    a = [r for r in rows if r["arm"] == arm]
    m = [x for x in all_units if x["arm"] == arm]
    ar = sum(r["verdict"] == "right" for r in a)
    print(f"ARM {arm}: {ar} right of {len(m)} made ({len(a)} delivered); cost an answer ${sum(r['cost'] for r in a) / max(len(a), 1):.4f}; "
          f"total ${sum(r['cost'] for r in a):.2f}; seconds an answer {sum(r['seconds'] for r in a) / max(len(a), 1):.0f}")
print(f"BAR 5  total cost of the {len(rows)} delivered answers: ${sum(r['cost'] for r in rows):.2f}   (bar: run within $7.00; N1/N2 at most $0.02 an answer)")
print(f"BAR 6  answers made but not delivered: {len(all_units) - len(rows)} of {len(all_units)}   (bar: at most 5)")
# the comparison, N3..N6 against O, on the 56 questions
cmp_q = {m["question"] for m in all_units if m["arm"] in ("N3", "N4", "N5", "N6")}
def right_of(arms, q=None):
    return sum(1 for r in rows if r["arm"] in arms and r["verdict"] == "right" and (q is None or r["group"] == q))
n_r = right_of(("N3", "N4", "N5", "N6")); o_r = right_of(("O",))
print(f"COMPARISON groups 10-13 ({len(cmp_q)} questions): N right {n_r}, O right {o_r}, N - O = {n_r - o_r:+d}   "
      f"(better at +5 or more; no difference shown between -3 and +4; worse at -4 or less)")
for g, arm in ((10, "N3"), (11, "N4"), (12, "N5"), (13, "N6")):
    print(f"   group {g}: N {right_of((arm,))} right, O {right_of(('O',), g)} right, of 14")
per_q: dict = defaultdict(Counter)
for r in rows:
    per_q[r["q"]]["n"] += 1
    per_q[r["q"]]["right"] += r["verdict"] == "right"
print("EVERY ANSWER NOT RIGHT (all arms):")
for r in sorted(rows, key=lambda r: (r["group"], int(r["q"][1:]), r["arm"])):
    if r["verdict"] != "right":
        print(f"  {r['q']} {r['arm']} {r['code']} {r['verdict']} confirmed={r['confirmed']} "
              f"points={r['points']} cautions={len(r['cautions'])} figures={str(r['figures'])[:80]}")
        for c in r["cautions"]:
            print("      caution:", c[:180])
