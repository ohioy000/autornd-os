"""The final tally's figures, read off the records and the readers' verdicts. Free.

    python -I docs/probes/final_tally_analysis.py REPO CODES_JSON VERDICTS_GLOB [FINAL_JSON]

Adapted from holdout2_analysis.py. CODES_JSON is the file final_tally_packets.py kept back from the readers (every unit of
both runs, where each came from, its set, arm, invocation and run); VERDICTS_GLOB matches the blind readers' files (a quoted
glob, one pattern); FINAL_JSON, when given, is code -> {"verdict": ...}: the executor's reading, which overrides the blind
reader where the two differ. REPO is the tree whose code rebuilds each delivery's cautions from the stored phase rows: a
rebuild that does not match the cautions the run recorded stops the script. When that tree has `routes._gaps` (branch
fix/20261123-caution-flaw), the gap cautions are read off the same rows and reported beside the shipped ones.

It prints the bars of docs/preregistration-20261123-final-tally.md and its amendment 1: right on the unseen set (bar 1), no
set collapsing (2), no confirmation beside a wrong figure (3), right answers coming clean (4), wrong answers marked (5), cost
(6), the delivery (7), each seat served as set (8); the tally by set and in the two groups; and the comparison of arm E
(the 56 field questions on the engineering profile) with arm F (the same 56 on their own profiles).
A unit the provider's key limit stopped (an HTTP 403 in its error) was not made: it is left out, and the resumed unit that
replaced it is the question's answer.
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
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION", "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"

from autornd.api import routes  # noqa: E402

GLOBAL = os.environ.get("TALLY_GLOBAL_MODEL", "deepseek/deepseek-v4.1-flash-1017")
TRIAGE = os.environ.get("TALLY_TRIAGE_MODEL", "tencent/hy4-flash")
USED = ("professional", "professional-hard", "professional-misleading", "professional-holdout", "tier2", "golden", "tier4")
UNSEEN = "professional-holdout-2"
POINTING = ("give different figures for the same thing", "is in none of the passages found")

verdicts: dict = {}
for path in sorted(glob.glob(sys.argv[3])):
    verdicts.update({k: v for k, v in json.loads(Path(path).read_text()).items() if isinstance(v, dict)})
final: dict = {}
if len(sys.argv) > 4:
    final = json.loads(Path(sys.argv[4]).read_text())


def question_text(set_name: str, qid: str) -> str:
    if set_name.startswith("professional"):
        f = {"professional": "questions.json", "professional-hard": "hard-questions.json",
             "professional-misleading": "misleading-questions.json", "professional-holdout": "holdout-questions.json",
             "professional-holdout-2": "holdout2-questions.json"}[set_name]
        return next(q["question"] for q in json.loads((REPO / "evals/professional" / f).read_text())["questions"] if q["id"] == qid)
    if set_name == "tier2":
        return next(q["question"] for q in json.loads((REPO / "evals/tier2/questions.json").read_text()) if q["id"] == qid)
    if set_name == "golden":
        g = json.loads((REPO / "evals/golden/keys.json").read_text())
        return next(x["request"] for x in g["golden"] + [g["side_test"]] if x["id"] == qid)
    for batch in ("pilot", "batch2", "batch3", "batch4", "batch5", "batch6"):
        for c in json.loads((REPO / f"evals/tier4/{batch}/candidates.json").read_text()):
            if c["id"] == qid:
                return c["request"]
    raise SystemExit(f"no question text for {set_name} {qid}")


def group_of(set_name: str, qid: str) -> int | None:
    """The second hold-out set's own groups: blocks of 14 ids, Y1-14 is group 1. No other set has any."""
    return (int(qid[1:]) - 1) // 14 + 1 if set_name == UNSEEN else None


_lines: dict[str, list] = {}
_phases: dict[str, list] = {}


def unit(source: str) -> dict:
    path, n = source.rsplit("#", 1)
    if path not in _lines:
        _lines[path] = [json.loads(x) for x in open(path, encoding="utf-8")]
    return _lines[path][int(n)]


def delivery(source: str, set_name: str, question: str):
    """The delivery rebuilt from the stored rows exactly as `_detail` builds it (see holdout2_analysis.py), and, when this
    tree has them, the gap cautions. A rebuild that does not match the shipped cautions stops the script."""
    path, n = source.rsplit("#", 1)
    phases_path = str(Path(path).parent / ("phases-" + Path(path).name))
    if phases_path not in _phases:
        _phases[phases_path] = [json.loads(x) for x in open(phases_path, encoding="utf-8")]
    rows_ = _phases[phases_path]
    workflow = [r for r in rows_ if r["kind"] == "workflow"][int(n)]
    if question_text(set_name, question)[:40] not in workflow["request"]:
        raise SystemExit(f"{source}: workflow {workflow['id']} is not {set_name} {question}")
    phases = sorted((r for r in rows_ if r["kind"] == "phase" and r["workflow_id"] == workflow["id"]),
                    key=lambda r: r["created_at"])
    verdicts_ = [(r["phase"], json.loads(json.dumps(r["verdict"]))) for r in phases]
    answer = next((v.get("summary") for name, v in reversed(verdicts_) if name == "implement" and isinstance(v, dict)), None)
    vote = next((v for name, v in reversed(verdicts_) if name == "recompute_vote"), None)
    sources = [v for name, v in verdicts_ if name == "sources"]
    vote = routes._settled(verdicts_, vote, sources)
    results = next((v.get("results") for name, v in reversed(verdicts_) if name == "implement" and isinstance(v, dict)), None)
    differing = routes._differing(sources)
    backed, unconfirmed = routes._checked_figures(results, sources, differing)
    if vote is not None and backed:
        vote = dict(vote, backed_by_source=backed)
    asked = next((len(v.get("asks") or []) for name, v in reversed(verdicts_) if name == "asks" and isinstance(v, dict)), 0)
    cautions = routes._cautions(vote, sources, answer is not None, asked, unconfirmed, differing,
                                calculation=routes._judged_a_calculation(verdicts_))
    figures = [(r.get("ask"), r.get("value")) for r in results or [] if isinstance(r, dict)]
    gaps = routes._gaps(verdicts_, workflow["request"]) if hasattr(routes, "_gaps") and answer is not None else None
    # What the decision tier already judged and stored (switch quote_answers, one record per quote found on its page; each
    # record's `choice` is the model's answer by the switch's thresholds). Read per answer in the secondary measure below.
    switched = next((v for name, v in reversed(verdicts_) if name == "answer_switches" and isinstance(v, dict)), None)
    choices = [r.get("choice") for r in (switched or {}).get("records") or [] if r.get("switch") == "quote_answers"]
    quotes = {"judged": len(choices), **{c: choices.count(c) for c in ("yes", "unsure", "no", "unavailable")}}
    return ((backed if routes._confirmations(backed, True) else []), figures, cautions, gaps,
            routes._judged_a_calculation(verdicts_), quotes)


made_codes = {c: m for c, m in CODES.items() if "403" not in (m.get("error") or "")}
stopped = len(CODES) - len(made_codes)
rows, all_units = [], []
for code, meta in made_codes.items():
    u = unit(meta["source"])
    key = (meta["set"], meta["question"])
    mb = u.get("models_by_function") or {}
    seat_ok = (not mb.get("engineering") or mb["engineering"] == [GLOBAL]) and \
              (not mb.get("triage") or mb["triage"] == [TRIAGE]) and "reader" not in mb
    base = {"code": code, "set": meta["set"], "q": meta["question"], "arm": meta["arm"], "run": meta["run"],
            "inv": meta["invocation"], "group": group_of(*key), "delivered": meta["delivered"], "status": meta["status"],
            "cost": float(u.get("cost") or 0) + float(u.get("liability") or 0), "seconds": float(u.get("seconds") or 0),
            "seat_ok": seat_ok, "mb": mb, "error": meta.get("error") or "", "source": meta["source"],
            "screen": (u.get("scorer") or {}).get("verdict")}
    all_units.append(base)
    if not meta["delivered"]:
        continue
    verdict = (final.get(code) or verdicts.get(code) or {}).get("verdict", "MISSING")
    backed, figures, rebuilt, gaps, calculation, quotes = delivery(meta["source"], meta["set"], meta["question"])
    cautions = u.get("cautions") or []
    if rebuilt != cautions:
        raise SystemExit(f"{meta['source']}: the rebuilt cautions are not the shipped ones")
    rows.append(dict(base, verdict=verdict, cautions=cautions, gaps=gaps,
                     points=any(p in c for c in cautions for p in POINTING),
                     confirmed=bool(backed), backed=backed, figures=figures, calculation=calculation, quotes=quotes))

tally_units = [u for u in all_units if u["arm"] != "E"]
tally_rows = [r for r in rows if r["arm"] != "E"]
right = [r for r in tally_rows if r["verdict"] == "right"]
wrong = [r for r in tally_rows if r["verdict"] != "right"]
n_dist = len({(u["set"], u["q"]) for u in tally_units})
print(f"units in the records {len(CODES)}; stopped by the key's limit and left out {stopped}; made {len(all_units)} "
      f"(arm E {len(all_units) - len(tally_units)}, the tally {len(tally_units)} over {n_dist} distinct questions)")
print(f"answers read {len(rows)} of {len(all_units)} made; missing verdicts {sum(r['verdict'] == 'MISSING' for r in rows)}; "
      f"unclear {sum(r['verdict'] == 'unclear' for r in rows)}")
dup = Counter((u["set"], u["q"]) for u in tally_units)
print("questions made more than once in the tally (should be none):", [k for k, v in dup.items() if v > 1])

unseen_units = [u for u in tally_units if u["set"] == UNSEEN]
unseen_right = [r for r in tally_rows if r["set"] == UNSEEN and r["verdict"] == "right"]
print(f"\nBAR 1  right on the unseen set: {len(unseen_right)} of {len(unseen_units)} made   (bar: at least 138 of 174)")
print("BAR 2  no set collapses (each set and each group of the unseen set at least 50% right of those made):")
by_set: dict = defaultdict(Counter)
for u in tally_units:
    by_set[u["set"]]["made"] += 1
    by_set[u["set"]]["delivered"] += u["delivered"]
for r in tally_rows:
    by_set[r["set"]]["right"] += r["verdict"] == "right"
for s in USED + (UNSEEN,):
    c = by_set[s]
    if c["made"]:
        print(f"   {s:26s} {c['right']:3d} right of {c['made']:3d} made ({c['delivered']} delivered) = {100 * c['right'] / c['made']:5.1f}%"
              f"{'   (a set under 25 questions: reported, not read as a rate)' if c['made'] < 25 else ''}")
by_group: dict = defaultdict(Counter)
for u in unseen_units:
    by_group[u["group"]]["made"] += 1
for r in tally_rows:
    if r["set"] == UNSEEN:
        by_group[r["group"]]["right"] += r["verdict"] == "right"
for g in sorted(by_group):
    c = by_group[g]
    print(f"   group {g:2d} of the unseen set    {c['right']:3d} right of {c['made']:3d} = {100 * c['right'] / c['made']:5.1f}%")
used_units = [u for u in tally_units if u["set"] in USED]
used_right = [r for r in tally_rows if r["set"] in USED and r["verdict"] == "right"]
print(f"   the seven sets used to build the harness: {len(used_right)} right of {len(used_units)} made = "
      f"{100 * len(used_right) / max(len(used_units), 1):.1f}%; the unseen set: {len(unseen_right)} of {len(unseen_units)} = "
      f"{100 * len(unseen_right) / max(len(unseen_units), 1):.1f}%; all {len(right)} of {len(tally_units)} = "
      f"{100 * len(right) / max(len(tally_units), 1):.1f}%")
print(f"\nBAR 3  not-right answers carrying a confirmation: {sum(r['confirmed'] for r in wrong)} of {len(wrong)} "
      f"(whether the ask it covers is the wrong one is read off the listing below)")
print(f"BAR 4  right answers with no caution: {sum(not r['cautions'] for r in right)} of {len(right)}   (bar: at least half)")
print(f"BAR 5  wrong answers with a pointing caution (the two phrases): {sum(r['points'] for r in wrong)} of {len(wrong)}   "
      f"(bar: at least half; any other caution is read by hand below)")
total_cost = sum(u["cost"] for u in all_units)
every_cost = sum(float(unit(m["source"]).get("cost") or 0) + float(unit(m["source"]).get("liability") or 0) for m in CODES.values())
print(f"BAR 6  cost of every unit of both runs, the stopped ones included: ${every_cost:.4f}; of the made ones ${total_cost:.4f}; "
      f"mean of the {len(tally_rows)} delivered tally answers ${sum(r['cost'] for r in tally_rows) / max(len(tally_rows), 1):.4f}   "
      f"(bar: within $9.00 with the probes' $0.0344; at most $0.02 an answer)")
blocked = [u for u in tally_units if not u["delivered"]]
print(f"BAR 7  tally answers that ended blocked or raised: {len(blocked)} of {len(tally_units)} (+{len(all_units) - len(tally_units)} of arm E: "
      f"{sum(not u['delivered'] for u in all_units if u['arm'] == 'E')})   (bar: at most 9 of the 367)")
for u in blocked:
    print(f"       {u['set']} {u['q']} {u['inv']} {u['run']} {u['status']} {u['error'][:110]}")
bad_seat = [u for u in all_units if not u["seat_ok"]]
reader = [u for u in all_units if "reader" in u["mb"]]
print(f"BAR 8  units whose engineering seat was not the global answer model or triage seat not the second triage model: "
      f"{len(bad_seat)}; units with a call on a reader tier: {len(reader)}   (bar: none)")
funcs: dict = defaultdict(Counter)
for u in all_units:
    for f, models in u["mb"].items():
        for m in models:
            funcs[f][m] += 1
print("       served, by function:", {f: dict(c) for f, c in sorted(funcs.items())})

print("\nCOMPARISON arm E against arm F on the 56 field questions (right on the key):")
e_rows = {r["q"]: r for r in rows if r["arm"] == "E"}
f_rows = {r["q"]: r for r in rows if r["arm"] == "F"}
f_made = {u["q"] for u in all_units if u["arm"] == "F"}
e_made = {u["q"] for u in all_units if u["arm"] == "E"}
both = sorted(f_made & e_made, key=lambda q: int(q[1:]))
fr = sum(1 for q in both if f_rows.get(q, {}).get("verdict") == "right")
er = sum(1 for q in both if e_rows.get(q, {}).get("verdict") == "right")
print(f"   questions made on both arms {len(both)} of 56; F right {fr}, E right {er}, F - E = {fr - er:+d}   "
      f"(better at +4 or more; no difference shown from -3 to +3; worse at -4 or less)")
for g in (10, 11, 12, 13):
    qs = [q for q in both if group_of(UNSEEN, q) == g]
    print(f"   group {g}: F {sum(f_rows.get(q, {}).get('verdict') == 'right' for q in qs)} right, "
          f"E {sum(e_rows.get(q, {}).get('verdict') == 'right' for q in qs)} right, of {len(qs)}")
pairs = Counter((f_rows.get(q, {}).get("verdict") == "right", e_rows.get(q, {}).get("verdict") == "right") for q in both)
print(f"   pairs (F right, E right): both {pairs[(True, True)]}, F only {pairs[(True, False)]}, E only {pairs[(False, True)]}, neither {pairs[(False, False)]}")
e_cost = sum(r["cost"] for r in rows if r["arm"] == "E")
print(f"   arm E cost ${e_cost:.4f} over {len(e_rows)} delivered; arm F ${sum(r['cost'] for r in rows if r['arm'] == 'F'):.4f}")

print("\nSCREENS (tier2 and golden scripts), beside the reading, never the result:")
for s in ("tier2", "golden"):
    rs = [r for r in tally_rows if r["set"] == s]
    agree = sum((r["screen"] == "PASS") == (r["verdict"] == "right") for r in rs if r["screen"])
    print(f"   {s}: screen PASS on {sum(r['screen'] == 'PASS' for r in rs)} of {len(rs)}; reading right on "
          f"{sum(r['verdict'] == 'right' for r in rs)}; they agree on {agree}")

print("\nEVERY ANSWER NOT RIGHT (the tally and arm E):")
for r in sorted([r for r in rows if r["verdict"] != "right"], key=lambda r: (r["set"], r["q"], r["arm"])):
    print(f"  {r['set']} {r['q']} {r['arm']} {r['run']} {r['code']} {r['verdict']} confirmed={r['confirmed']} points={r['points']} "
          f"cautions={len(r['cautions'])} gaps={None if r['gaps'] is None else len(r['gaps'])} figures={str(r['figures'])[:80]}")
    for c in r["cautions"]:
        print("      caution:", c[:180])
    for g in r["gaps"] or []:
        print("      gap:", g[:180])
if hasattr(routes, "_gaps"):
    r_all = [r for r in rows if r["verdict"] == "right"]
    n_all = [r for r in rows if r["verdict"] != "right"]
    gr = sum(bool(r["gaps"]) for r in r_all)
    gn = sum(bool(r["gaps"]) for r in n_all)
    sr = sum(bool(r["cautions"]) for r in r_all)
    sn = sum(bool(r["cautions"]) for r in n_all)
    er_ = sum(bool(r["cautions"] or r["gaps"]) for r in r_all)
    en_ = sum(bool(r["cautions"] or r["gaps"]) for r in n_all)
    print(f"\nTHE GAP CAUTIONS (branch fix/20261123-caution-flaw, replayed; all {len(rows)} delivered answers, arm E included):")
    print(f"   shipped cautions beside right {sr} of {len(r_all)} ({100 * sr / max(len(r_all), 1):.1f}%), beside not-right {sn} of {len(n_all)}")
    print(f"   gap cautions     beside right {gr} of {len(r_all)} ({100 * gr / max(len(r_all), 1):.1f}%), beside not-right {gn} of {len(n_all)}"
          f"   (design: right answers marked at most 3 percent; every not-right one marked pointing at the wrong part, read by hand)")
    print(f"   either           beside right {er_} of {len(r_all)}, beside not-right {en_} of {len(n_all)}")
    print("   RIGHT ANSWERS THAT GET A GAP:")
    for r in r_all:
        if r["gaps"]:
            print(f"      {r['set']} {r['q']} {r['arm']} {r['code']}: {[g[:90] for g in r['gaps']]}")

# ---- A secondary measure, written down on 2026-11-23 before any answer of the tally was read ---------------------------------
# The owner asked whether the decision tier could serve the caution fix. It already judges, for every quote a lookup found on its
# page, whether the passage states an answer to the question it was quoted for (switch quote_answers, live as a label), and the
# judgments are stored with every run, so reading them per answer costs no call. The rule is one and is not tuned: the lookup
# found quotes and none was judged to state an answer (no confident yes). On the 681 labelled answers of four earlier runs
# (docs/probes/caution_replay.py's pool) it held for 114 of 658 right answers (17.3%) and 11 of 23 not right (47.8%), and for 4 of
# the 11 not-right answers that come clean, with 86 right answers beside them: a weak separation, found in-sample. This reads it
# on answers made after it was stated. It is a measurement: no caution is built on it, and it is reported as read.
if rows:
    r_all = [r for r in rows if r["verdict"] == "right"]
    n_all = [r for r in rows if r["verdict"] != "right"]
    judged = lambda r: r["quotes"]["judged"] > 0
    no_yes = lambda r: judged(r) and r["quotes"]["yes"] == 0
    clean = lambda r: not (r["cautions"] or r["gaps"])
    share = lambda grp, f: f"{sum(bool(f(r)) for r in grp):4d} of {len(grp):3d} ({100 * sum(bool(f(r)) for r in grp) / max(len(grp), 1):5.1f}%)"
    print(f"\nTHE DECISION TIER'S OWN JUDGMENTS OF THE QUOTES, per answer (secondary; all {len(rows)} delivered answers, arm E included):")
    print(f"   {'':58s}{'right':24s}not right")
    for label, f in (("the lookup found a quote on its page, so the tier judged one", judged),
                     ("the shipped label: some quote judged not to answer", lambda r: r["quotes"]["no"] > 0),
                     ("NO QUOTE JUDGED TO STATE AN ANSWER (the rule)", no_yes),
                     ("  ... and not a request judged a calculation", lambda r: no_yes(r) and not r["calculation"]),
                     ("  ... and the answer otherwise comes clean", lambda r: no_yes(r) and clean(r)),
                     ("every judgment a confident no (none unsure)", lambda r: judged(r) and r["quotes"]["yes"] == 0 and r["quotes"]["unsure"] == 0)):
        print(f"   {label:58s}{share(r_all, f):24s}{share(n_all, f)}")
    print(f"   the answers that come clean (no shipped and no gap caution{'' if hasattr(routes, '_gaps') else '; this tree has no gaps'}): "
          f"right {share(r_all, clean)}, not right {share(n_all, clean)}")
    print("   EVERY ANSWER NOT RIGHT, its quotes judged yes/unsure/no and whether it comes clean:")
    for r in sorted(n_all, key=lambda r: (r["set"], r["q"], r["arm"])):
        q = r["quotes"]
        print(f"      {r['set']} {r['q']} {r['arm']} {r['code']} {r['verdict']}: {q['yes']}/{q['unsure']}/{q['no']}"
              f"{' (unavailable ' + str(q['unavailable']) + ')' if q['unavailable'] else ''}  rule={'YES' if no_yes(r) else 'no'}  "
              f"comes clean={clean(r)}")

print("\nBY RUN (which run made each answer):", dict(Counter((u["run"], u["delivered"]) for u in all_units)))
