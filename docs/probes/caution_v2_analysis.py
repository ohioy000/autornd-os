"""The revised caution fix on new answers (docs/preregistration-20261123-caution-v2-test.md). Free.

    python -I docs/probes/caution_v2_analysis.py REPO CODES_JSON VERDICTS_GLOB [FINAL_JSON] [BASELINE_CODES_JSON]

CODES_JSON is caution_v2_packets.py's codes file; VERDICTS_GLOB the blind readers' files; FINAL_JSON the executor's reading (code ->
{"verdict": ...}), which overrides the blind reader. REPO is the tree whose code rebuilds each delivery's cautions from the stored
phase rows (a rebuild that does not match the recorded cautions stops the script) and reads the gap cautions off the same rows.
Prints, by group (A: questions whose right answers carried a gap; B: questions with a not-right answer; C: the seeded control):
answers, right and not right; gap cautions beside right answers, by kind; gap cautions beside not-right answers, each with the
reader's note so that whether it points at the wrong part can be read by hand; the not-right answers that come clean; the share of
lookups that read a page in full for which the words of a proof were named (the preregistered 60 percent), beside the same figure
for the second hold-out run in the tally (BASELINE_CODES_JSON, the final tally's codes file); and which channel each right "none
stated" answer used.
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

UNSEEN = "professional-holdout-2"
POINTING = ("give different figures for the same thing", "is in none of the passages found")
GROUP_A = {("professional-holdout-2", q) for q in ("Y4", "Y89", "Y104", "Y129", "Y158")} | \
          {("professional-holdout", q) for q in ("X22", "X36", "X19")}
GROUP_B = {("professional-holdout", q) for q in ("X12", "X14", "X20", "X31", "X41", "X8")} | \
          {("professional-holdout-2", q) for q in ("Y115", "Y124", "Y170", "Y37", "Y68", "Y88", "Y9")} | \
          {("tier4", "T4-42"), ("tier4", "T4-58")}

verdicts: dict = {}
for path in sorted(glob.glob(sys.argv[3])):
    verdicts.update({k: v for k, v in json.loads(Path(path).read_text()).items() if isinstance(v, dict)})
final: dict = {}
if len(sys.argv) > 4 and sys.argv[4] != "-":
    final = json.loads(Path(sys.argv[4]).read_text())
BASELINE = json.loads(Path(sys.argv[5]).read_text()) if len(sys.argv) > 5 else {}


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
    # What the live routing switches settled for this answer, read off the stored rows: the calculation switch's route (whether
    # the three-sample recompute may run), the lookup switch's choice, and whether the recompute and a lookup actually ran.
    route = next(((v.get("route") or {}).get("needs_calculation") for name, v in reversed(verdicts_)
                  if name == "request_switches" and isinstance(v, dict)), None)
    looked = [r.get("choice") for name, v in verdicts_ if name == "switches" and isinstance(v, dict)
              for r in v.get("records") or [] if r.get("switch") == "needs_sources"]
    voted = next((v for name, v in reversed(verdicts_) if name == "recompute_vote" and isinstance(v, dict)), None)
    routing = {"calculation": route, "sources": looked[-1] if looked else None,
               "recompute_ran": bool(voted) and not voted.get("skipped"), "lookup_ran": any(n == "sources" for n, _ in verdicts_)}
    return ((backed if routes._confirmations(backed, True) else []), figures, cautions, gaps,
            routes._judged_a_calculation(verdicts_), quotes, routing)



def group_name(set_name: str, q: str) -> str:
    return "A" if (set_name, q) in GROUP_A else ("B" if (set_name, q) in GROUP_B else "C")


def proof_state(source: str) -> tuple[bool, bool, set[int]]:
    """(a lookup read at least one page, words were named for at least one ask, the asks the answer calls not stated)."""
    path, n = source.rsplit("#", 1)
    phases_path = str(Path(path).parent / ("phases-" + Path(path).name))
    if phases_path not in _phases:
        _phases[phases_path] = [json.loads(x) for x in open(phases_path, encoding="utf-8")]
    rows_ = _phases[phases_path]
    workflow = [r for r in rows_ if r["kind"] == "workflow"][int(n)]
    findings = [f for r in rows_ if r["kind"] == "phase" and r["workflow_id"] == workflow["id"] and r["phase"] == "sources"
                for f in (r["verdict"].get("findings") or [])]
    read = any(f.get("documents") for f in findings)
    named = any(any(terms for terms in (f.get("searched") or {}).values()) for f in findings)
    return read, named, set()


rows = []
for code, meta in CODES.items():
    if not meta["delivered"]:
        continue
    verdict = (final.get(code) or verdicts.get(code) or {}).get("verdict", "MISSING")
    note = (verdicts.get(code) or {}).get("note", "")
    backed, figures, rebuilt, gaps, calculation, quotes, routing = delivery(meta["source"], meta["set"], meta["question"])
    u = unit(meta["source"])
    # This run's code delivers the gap cautions itself (they stand after the others in `_detail`), so the recorded cautions are
    # the rebuilt ones plus the gaps; the rebuild is checked against that, and the shipped cautions are the rebuilt ones.
    if rebuilt + (gaps or []) != (u.get("cautions") or []):
        raise SystemExit(f"{meta['source']}: the rebuilt cautions and gaps are not the recorded ones")
    read, named, _ = proof_state(meta["source"])
    path, n = meta["source"].rsplit("#", 1)
    phases = [r for r in _phases[str(Path(path).parent / ("phases-" + Path(path).name))] if r["kind"] == "phase"]
    wf = [r for r in _phases[str(Path(path).parent / ("phases-" + Path(path).name))] if r["kind"] == "workflow"][int(n)]
    impl = next((r["verdict"] for r in sorted((r for r in phases if r["workflow_id"] == wf["id"] and r["phase"] == "implement"),
                                              key=lambda r: r["created_at"])[::-1]), {}) or {}
    rows.append({"code": code, "set": meta["set"], "q": meta["question"], "group": group_name(meta["set"], meta["question"]),
                 "verdict": verdict, "note": note, "gaps": gaps or [], "cautions": rebuilt,
                 "read": read, "named": named, "not_stated": bool(impl.get("not_stated")), "blocked": bool(impl.get("blocked_on")),
                 "results": len(impl.get("results") or []), "cost": float(u.get("cost") or 0), "mb": u.get("models_by_function") or {}})

right = lambda r: r["verdict"] == "right"
bad = lambda r: r["verdict"] in ("wrong", "partly")
# This run's tree (the caution branch) does not carry the probe change that records `models_by_function`, so the seats are read from the
# stored phase rows' `model_used`, and the reader tier from the documents' own `reader` records (its served model is not recorded).
seats = Counter()
reader_calls = documents_read = documents_with_reader = 0
for path in {str(Path(m["source"].rsplit("#", 1)[0]).parent / "phases-shard-0.jsonl") for m in CODES.values()}:
    for r in _phases.get(path) or [json.loads(x) for x in open(path, encoding="utf-8")]:
        if r["kind"] != "phase":
            continue
        if r.get("model_used"):
            seats[(r["phase"], r["model_used"])] += 1
        if r["phase"] == "sources":
            for f in r["verdict"].get("findings") or []:
                for d in f.get("documents") or []:
                    documents_read += 1
                    if "reader" in d:
                        documents_with_reader += 1
                        reader_calls += d["reader"].get("calls", 0)
print(f"v2 answers delivered {len(rows)} of {len(CODES)} units; verdicts {dict(Counter(r['verdict'] for r in rows))}; "
      f"cost of the delivered ${sum(r['cost'] for r in rows):.4f}")
print(f"reader tier: {documents_with_reader} of {documents_read} documents read by it, {reader_calls} calls; seats by phase: "
      + "; ".join(f"{k[0]} {k[1]} x{v}" for k, v in sorted(seats.items(), key=lambda x: -x[1]) if k[0] in ("triage", "implement", "recompute", "request_switches")))
KIND = (("gives no result", "no result"), ("could not answer", "blocked note"), ("is not stated in the document", "not stated"),
        ("words long", "short text"))
def kinds(r):
    return sorted({k for g in r["gaps"] for needle, k in KIND if needle in g})
print("\nBY GROUP (gap = the revised gap cautions):")
for grp in "ABC":
    g = [r for r in rows if r["group"] == grp]
    gr, gb = [r for r in g if right(r)], [r for r in g if bad(r)]
    print(f"  {grp}: {len(g)} answers, right {len(gr)}, not right {len(gb)}; gap beside right {sum(bool(r['gaps']) for r in gr)}"
          f" ({100 * sum(bool(r['gaps']) for r in gr) / max(1, len(gr)):.1f}%), beside not right {sum(bool(r['gaps']) for r in gb)} of {len(gb)}")
ar = [r for r in rows if right(r) and r["group"] in "AC"]
print(f"\nFALSE ALARMS, preregistered measure (right answers of A and the control): {sum(bool(r['gaps']) for r in ar)} of {len(ar)} "
      f"({100 * sum(bool(r['gaps']) for r in ar) / max(1, len(ar)):.1f}%; bar 3%)")
print("  by kind, over every right answer:", dict(Counter(k for r in rows if right(r) for k in kinds(r))))
print("\nRIGHT ANSWERS THAT GET A GAP:")
for r in rows:
    if right(r) and r["gaps"]:
        print(f"   {r['set']} {r['q']} {r['group']} {r['code']} results={r['results']} not_stated={r['not_stated']} blocked={r['blocked']}: "
              + " || ".join(g[:170] for g in r["gaps"]))
print("\nEVERY ANSWER NOT RIGHT (read the gap against the reader's note for 'points at the wrong part'):")
for r in rows:
    if bad(r):
        print(f"   {r['set']} {r['q']} {r['group']} {r['code']} {r['verdict']} gaps={len(r['gaps'])} shipped={len(r['cautions'])} "
              f"clean={not r['gaps'] and not r['cautions']}\n      reader: {r['note'][:240]}")
        for g in r["gaps"]:
            print("      gap:", g[:260])
        for c in r["cautions"]:
            print("      shipped:", c[:200])
nb = [r for r in rows if bad(r)]
print(f"\nCATCHES: gap beside {sum(bool(r['gaps']) for r in nb)} of {len(nb)} not-right answers; shipped-or-gap "
      f"{sum(bool(r['gaps'] or r['cautions']) for r in nb)}; come clean {sum(not r['gaps'] and not r['cautions'] for r in nb)}")
print("\nPROOFS OF ABSENCE (the words were named for a lookup that read a page; bar 60%):")
def cover(rs):
    e = [r for r in rs if r["read"]]
    return f"{sum(r['named'] for r in e)} of {len(e)} ({100 * sum(r['named'] for r in e) / max(1, len(e)):.1f}%)"
print("  this run, all answers:", cover(rows))
for grp in "ABC":
    print(f"    group {grp}:", cover([r for r in rows if r["group"] == grp]))
if BASELINE:
    base = []
    for code, meta in BASELINE.items():
        if meta["delivered"] and meta["set"] == UNSEEN and meta["arm"] != "E":
            read, named, _ = proof_state(meta["source"])
            base.append({"read": read, "named": named})
    print("  the tally's second hold-out answers:", cover(base))
print("\nTHE 'NONE STATED' ANSWERS (right answers of X36, X19, and any answer that used either channel):")
for r in rows:
    if r["not_stated"] or (r["q"] in ("X36", "X19") and right(r)):
        print(f"   {r['q']} {r['code']} {r['verdict']} not_stated_channel={r['not_stated']} blocked_note={r['blocked']} "
              f"gaps={[g[:90] for g in r['gaps']]}")
