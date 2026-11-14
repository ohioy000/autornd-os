"""The figures in docs/reviews/2026-11-14-switches-alive.md, re-derived from
the committed traces. Free: it reads files and calls nothing.

    python docs/probes/switches_alive_analysis.py \
        docs/traces/20261114T162951Z-switches-alive

PREFIX-phases-shard-N.jsonl is each shard's database exported a row per line
(docs/probes/export_shard_db.py). From those rows this builds each run's
workflow and phase rows in memory and passes them to the API's own `_detail`,
so the delivery it checks is the one the API would return. For every unit it
compares the labels in that delivery with the decision records beside them
(the preregistration's "What counts as alive",
docs/preregistration-20261114-switches-alive.md):

  same_meaning   the asks in the vote's `cleared` are exactly the confident
                 yes records; `flagged` is true only if a disagreement is
                 left; a caution says the ask was worded differently; the
                 stored recompute_vote row still says what the vote found;
  quote_answers  the quotes carrying answers_question false are exactly the
                 found quotes whose record is a confident no, paired in the
                 order they were asked; a caution counts them.

It prints one line per unit, the totals and every mismatch. The hand reading
of the answers, pairs and passages is in the report, not here (D50).
"""
from __future__ import annotations

import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
# config.py exits at import without the six tiers, and pydantic reads the
# .env in the working directory: placeholders through the environment, as
# tests/conftest.py does. Nothing here calls a model.
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION",
             "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"

from autornd.api.routes import _detail  # noqa: E402
from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus  # noqa: E402

PREFIX = sys.argv[1]
YES_AT, NO_AT = 0.80, 0.20     # switches/default.yaml, both switches


def _when(text: str) -> datetime:
    return datetime.fromisoformat(text)


def rebuilt(path: str) -> list[Workflow]:
    """One shard's workflows with their phases, as the database held them."""
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    runs = {}
    for r in rows:
        if r["kind"] == "workflow":
            runs[r["id"]] = Workflow(
                id=r["id"], request=r["request"],
                status=WorkflowStatus[r["status"]], risk_level=r["risk_level"],
                iteration=0, total_cost=r["total_cost"],
                unreconciled_liability=r["unreconciled_liability"],
                error=r["error"], created_at=_when(r["created_at"]),
                updated_at=_when(r["created_at"]))
    for r in rows:
        if r["kind"] == "phase":
            runs[r["workflow_id"]].phases.append(PhaseResult(
                id=r["id"], workflow_id=r["workflow_id"], phase=r["phase"],
                iteration=r["iteration"], model_used=r["model_used"],
                cost=r["cost"], created_at=_when(r["created_at"]),
                verdict_json=json.dumps(r["verdict"])))
    return [runs[k] for k in sorted(runs)]


def check(w: Workflow) -> tuple[dict, list[str]]:
    d = _detail(w)
    problems: list[str] = []
    stored = next((json.loads(p.verdict_json) for p in
                   sorted(w.phases, key=lambda p: p.created_at, reverse=True)
                   if p.phase == "recompute_vote"), None) or {}
    vote = d.recompute_vote or {}
    sm = [r for r in d.decisions if r["switch"] == "same_meaning"]
    qa = [r for r in d.decisions if r["switch"] == "quote_answers"]

    want = sorted(int(r["item"].split()[1]) for r in sm
                  if r["probability"] is not None and r["probability"] >= YES_AT)
    got = sorted(int(a) for a in vote.get("cleared") or [])
    if want != got:
        problems.append(f"cleared {got}, confident yes on {want}")
    if got:
        left = [x.get("ask") for x in vote.get("disagreements") or []
                if x.get("ask") not in got]
        if vote.get("flagged") != (bool(vote.get("flagged_by_vote")) and bool(left)):
            problems.append(f"flagged {vote.get('flagged')} with {left} left")
        if not any("worded ask" in c for c in d.cautions):
            problems.append("no caution for the cleared ask")
        if not left and any("disagrees" in c for c in d.cautions):
            problems.append("a disagreement caution with nothing left")
        if stored.get("flagged") != vote.get("flagged_by_vote") or "cleared" in stored:
            problems.append("the stored vote row is not what the vote found")

    found = [q for s in d.sources for f in s.get("findings") or []
             for q in f.get("quotes") or [] if q.get("status") == "found"]
    if len(found) != len(qa):
        problems.append(f"{len(found)} found quotes, {len(qa)} quote_answers records")
    want_no = [i for i, r in enumerate(qa)
               if r["probability"] is not None and r["probability"] <= NO_AT]
    got_no = [i for i, q in enumerate(found) if q.get("answers_question") is False]
    if want_no != got_no:
        problems.append(f"labelled {got_no}, confident no on {want_no}")
    if any(i < len(found) and r["item"] != found[i].get("url")
           for i, r in enumerate(qa)):
        problems.append("a quote_answers record and its quote name other pages")
    counted = [c for c in d.cautions if "do not state an answer" in c]
    if bool(got_no) != bool(counted) or (counted and not counted[0].startswith(
            f"{len(got_no)} of the {len(found)} ")):
        problems.append(f"caution {counted} for {len(got_no)} labelled")

    switch_cost = sum(p.cost for p in w.phases if p.phase.endswith("switches"))
    return {"status": d.status, "cost": d.total_cost, "switch_cost": switch_cost,
            "sm_yes": len(want), "sm_asked": len(sm), "cleared": got,
            "flagged": vote.get("flagged"), "flagged_by_vote": vote.get("flagged_by_vote"),
            "qa_asked": len(qa), "qa_no": len(want_no),
            "qa_unsure": sum(1 for r in qa if r["choice"] == "unsure"),
            "qa_yes": sum(1 for r in qa if r["choice"] == "yes"),
            "labelled": len(got_no)}, problems


names = {}
for n, path in enumerate(sorted(glob.glob(f"{PREFIX}-shard-*.jsonl"))):
    for wid, line in enumerate(open(path, encoding="utf-8"), start=1):
        r = json.loads(line)
        names[(str(n), wid)] = f"{r['question']} r{r['repeat']}"

totals = {"cost": 0.0, "switch_cost": 0.0, "sm_asked": 0, "sm_yes": 0,
          "cleared": 0, "qa_asked": 0, "qa_no": 0, "qa_unsure": 0, "qa_yes": 0,
          "labelled": 0, "mismatches": 0, "completed": 0, "units": 0}
for path in sorted(glob.glob(f"{PREFIX}-phases-shard-*.jsonl")):
    n = path.rsplit("-", 1)[-1].removesuffix(".jsonl")
    for w in rebuilt(path):
        row, problems = check(w)
        print(f"{names[(n, w.id)]:8} {row['status']:9} ${row['cost']:.4f}"
              f"  same_meaning yes {row['sm_yes']}/{row['sm_asked']}"
              f" cleared {row['cleared']} flagged {row['flagged']}"
              f" (by vote {row['flagged_by_vote']})"
              f"  quote_answers no {row['qa_no']} unsure {row['qa_unsure']}"
              f" yes {row['qa_yes']} labelled {row['labelled']}"
              f"  {'OK' if not problems else problems}")
        totals["units"] += 1
        totals["completed"] += row["status"] == "completed"
        totals["mismatches"] += len(problems)
        totals["cleared"] += len(row["cleared"])
        for k in ("cost", "switch_cost", "sm_asked", "sm_yes", "qa_asked",
                  "qa_no", "qa_unsure", "qa_yes", "labelled"):
            totals[k] += row[k]
totals["cost"] = round(totals["cost"], 4)
totals["switch_cost"] = round(totals["switch_cost"], 6)
print(json.dumps(totals))
