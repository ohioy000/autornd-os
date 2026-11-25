"""The final tally's lanes (docs/preregistration-20261123-final-tally.md): plan them, probe them, start them.

    python -I docs/probes/final_tally_launch.py plan            # free: prints the lanes, their questions and caps
    python -I docs/probes/final_tally_launch.py probe           # paid, '$0.10' a set: one question of tier2, golden, tier4
    python -I docs/probes/final_tally_launch.py run             # paid: starts every lane, detached, and returns
    python -I docs/probes/final_tally_launch.py resume-plan     # free: the units the key's limit left unanswered, and caps
    python -I docs/probes/final_tally_launch.py resume          # paid: starts the lanes for those units only (amendment 1)
    python -I docs/probes/final_tally_launch.py rerun-plan [1|2]  # free: the re-ask run's lanes, questions and caps
    python -I docs/probes/final_tally_launch.py rerun [1|2]       # paid: starts them (docs/preregistration-20261123-caution-test.md)

Environment: TALLY_TREE (the clean checkout the runs use, default /home/jb/autornd-os-wt-h2run), TALLY_OUT (where the
runs write, outside any git tree, default /home/jb/final-runs), TALLY_PY (the interpreter).

A lane is a shell script that runs its invocations of docs/probes/short_workflows_measurement.py one after the other;
an invocation is one MEASURE_SET, one profile, a list of question ids and a cap. The lanes run together. Nothing here
changes which questions run or how: the runner does that, as it did for the second hold-out run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TREE = Path(os.environ.get("TALLY_TREE", "/home/jb/autornd-os-wt-h2run"))
OUT = Path(os.environ.get("TALLY_OUT", "/home/jb/final-runs"))
PY = os.environ.get("TALLY_PY", "/home/jb/autornd-os/.venv/bin/python3")
PER_ANSWER_CAP = 0.022      # a cap is 1.6 times the expected cost an answer ('$0.0135'), so it rarely binds
MIN_CAP = 0.30
E_CAP = 0.45                # the small test: two processes of '$0.45'; the owner's cap on it is '$1.00'

PRO = {"professional": "questions.json", "professional-hard": "hard-questions.json",
       "professional-misleading": "misleading-questions.json", "professional-holdout": "holdout-questions.json",
       "professional-holdout-2": "holdout2-questions.json"}
FIELD_PROFILE = {10: "legal", 11: "finance", 12: "medical", 13: "science"}


def ids_of(path: str) -> list[str]:
    return [q["id"] for q in json.loads((REPO / path).read_text())["questions"]]


def group_of(qid: str) -> int:
    return (int(qid[1:]) - 1) // 14 + 1


Y = ids_of("evals/professional/holdout2-questions.json")
Y_ENG = [q for q in Y if group_of(q) <= 9]
Y_FIELD = {g: [q for q in Y if group_of(q) == g] for g in (10, 11, 12, 13)}
Y_56 = [q for g in (10, 11, 12, 13) for q in Y_FIELD[g]]
X = ids_of("evals/professional/holdout-questions.json")
TIER2 = [q["id"] for q in json.loads((REPO / "evals/tier2/questions.json").read_text())]
# golden Q1 to Q5 are tier-2's Q1 to Q5 in another notation (the runner says so; compared 2026-11-13): asked once,
# under tier2. Golden's own are Q6 and the side test.
GOLDEN = [q["id"] for q in json.loads((REPO / "evals/golden/keys.json").read_text())["golden"]
          if q["id"] not in ("Q1", "Q2", "Q3", "Q4", "Q5")] + \
    [json.loads((REPO / "evals/golden/keys.json").read_text())["side_test"]["id"]]


def tier4_ids() -> list[str]:
    out = []
    for name in ("pilot", "batch2", "batch3", "batch4", "batch5", "batch6"):
        out += [c["id"] for c in json.loads((REPO / "evals/tier4" / name / "candidates.json").read_text())]
    return out


def cap_for(n: int) -> float:
    return max(MIN_CAP, round(n * PER_ANSWER_CAP, 2))


def inv(name: str, measure_set: str, profile: str, ids: list[str], cap: float | None = None) -> dict:
    return {"name": name, "set": measure_set, "profile": profile, "ids": ids, "cap": cap or cap_for(len(ids))}


def lanes() -> list[list[dict]]:
    h = len(Y_ENG) // 4
    cuts = [0, h + 1, 2 * h + 2, 3 * h + 2, len(Y_ENG)]      # 30, 30, 29, 29 of the 118
    t4 = tier4_ids()
    p, hard, m = (ids_of(f"evals/professional/{PRO[s]}") for s in
                  ("professional", "professional-hard", "professional-misleading"))
    plan: list[list[dict]] = []
    for i in range(4):
        plan.append([inv(f"Y-eng-{i + 1}", "professional-holdout-2", "engineering", Y_ENG[cuts[i]:cuts[i + 1]])])
    plan.append([inv("X-1", "professional-holdout", "engineering", X[:21]),
                 inv("P", "professional", "engineering", p)])
    plan.append([inv("X-2", "professional-holdout", "engineering", X[21:]),
                 inv("H", "professional-hard", "engineering", hard)])
    plan.append([inv("T2", "tier2", "engineering", TIER2),
                 inv("G", "golden", "engineering", GOLDEN)])
    plan.append([inv("T4", "tier4", "engineering", t4),
                 inv("M", "professional-misleading", "engineering", m)])
    # the small test: the 56 field questions on the engineering profile (arm E), two processes
    half = len(Y_56) // 2
    plan.append([inv("E-1", "professional-holdout-2", "engineering", Y_56[:half], E_CAP)])
    plan.append([inv("E-2", "professional-holdout-2", "engineering", Y_56[half:], E_CAP)])
    # the same 56 on their own field profiles (arm F), as shipped
    plan.append([inv("F-legal", "professional-holdout-2", "legal", Y_FIELD[10]),
                 inv("F-finance", "professional-holdout-2", "finance", Y_FIELD[11])])
    plan.append([inv("F-medical", "professional-holdout-2", "medical", Y_FIELD[12]),
                 inv("F-science", "professional-holdout-2", "science", Y_FIELD[13])])
    return plan


def command(i: dict, out: Path) -> str:
    env = (f"PYTHONPATH={TREE} AUTORND_PROFILE={i['profile']} MEASURE_SET={i['set']} "
           f"MEASURE_WORKFLOWS=answer-and-recompute")
    return (f"{env} {PY} {TREE}/docs/probes/short_workflows_measurement.py {out}/{i['name']} 0 1 {i.get('repeats', 1)} {i['cap']} "
            f"{' '.join(i['ids'])} > {out}/{i['name']}.log 2>&1")


def write_lane(n: int, lane: list[dict], out: Path = OUT) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    (out / "lanes").mkdir(exist_ok=True)
    path = out / "lanes" / f"lane{n:02d}.sh"
    lines = ["#!/bin/bash", f"cd {TREE}"]
    for i in lane:
        lines += [f'echo "START {i["name"]} $(date -u +%T)" >> {out}/status.txt', command(i, out),
                  f'echo "EXIT {i["name"]} $? $(date -u +%T)" >> {out}/status.txt']
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o755)
    return path


def plan() -> None:
    total, cap_sum, count = 0, 0.0, 0
    for n, lane in enumerate(lanes(), 1):
        q = sum(len(i["ids"]) for i in lane)
        c = sum(i["cap"] for i in lane)
        total += q
        cap_sum += c
        print(f"lane {n:2d}: {q:3d} questions, caps ${c:.2f}: " +
              "; ".join(f"{i['name']} [{i['set']}, {i['profile']}, {len(i['ids'])}, ${i['cap']:.2f}]" for i in lane))
        count += len(lane)
    distinct = sum(len(i["ids"]) for lane in lanes() for i in lane if not i["name"].startswith("E-"))
    print(f"answers {total} ({distinct} distinct questions + {total - distinct} small-test answers), "
          f"invocations {count}, sum of caps ${cap_sum:.2f}")


def probe() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [inv("probe-tier2", "tier2", "engineering", TIER2[:1], 0.10),
            inv("probe-golden", "golden", "engineering", GOLDEN[:1], 0.10),
            inv("probe-tier4", "tier4", "engineering", tier4_ids()[-1:], 0.10)]
    procs = []
    for j in jobs:
        procs.append(subprocess.Popen(["bash", "-c", command(j, OUT)], cwd=TREE))
    sys.exit(max(p.wait() for p in procs))


def run() -> None:
    for n, lane in enumerate(lanes(), 1):
        script = write_lane(n, lane)
        subprocess.Popen(["bash", str(script)], start_new_session=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        print("started", script)


# ---- Amendment 1 (docs/preregistration-20261123-final-tally-amendment-1.md): the units the key's limit stopped ----
RESUME = Path(os.environ.get("TALLY_RESUME_OUT", str(OUT / "resume1")))
RESUME_PER_ANSWER_CAP = 0.022   # as the first run's
RESUME_TIER4_PER_ANSWER_CAP = 0.030   # the probe's tier-4 answer cost '$0.0209' (its pages ride in the message)
RESUME_MIN_CAP = 0.10
RESUME_E_CAP = 0.38             # the small test as a whole stays inside the owner's '$1.00': '$0.143' spent + 2 x '$0.38' + overrun


def unanswered(name: str) -> list[str]:
    """The ids, in their first order, of an invocation's units that the provider's key limit stopped: not delivered and an
    HTTP 403 in the error (a few had spent a little before it came). A unit that ended blocked for any other reason is a
    result and stays one."""
    path = OUT / name / "shard-0.jsonl"
    rows = [json.loads(x) for x in open(path, encoding="utf-8")] if path.exists() else []
    return [r["question"] for r in rows if not r.get("delivered") and "403" in str(r.get("error") or "")]


def resume_lanes() -> list[list[dict]]:
    out: list[list[dict]] = []
    for lane in lanes():
        mine = []
        for i in lane:
            ids = unanswered(i["name"])
            if not ids:
                continue
            if i["name"].startswith("E-"):
                cap = RESUME_E_CAP
            elif i["set"] == "tier4":
                cap = max(RESUME_MIN_CAP, round(len(ids) * RESUME_TIER4_PER_ANSWER_CAP, 2))
            else:
                cap = max(RESUME_MIN_CAP, round(len(ids) * RESUME_PER_ANSWER_CAP, 2))
            mine.append(dict(i, ids=ids, cap=cap))
        if mine:
            out.append(mine)
    return out


def resume_plan() -> None:
    total, cap_sum, count = 0, 0.0, 0
    for n, lane in enumerate(resume_lanes(), 1):
        q = sum(len(i["ids"]) for i in lane)
        c = sum(i["cap"] for i in lane)
        total += q
        cap_sum += c
        count += len(lane)
        print(f"lane {n:2d}: {q:3d} questions, caps ${c:.2f}: " +
              "; ".join(f"{i['name']} [{len(i['ids'])}, ${i['cap']:.2f}]" for i in lane))
    print(f"units to make {total}, invocations {count}, sum of caps ${cap_sum:.2f}")


def resume() -> None:
    for n, lane in enumerate(resume_lanes(), 1):
        script = write_lane(n, lane, RESUME)
        subprocess.Popen(["bash", str(script)], start_new_session=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        print("started", script)


# ---- The re-ask run (docs/preregistration-20261123-caution-test.md): fresh answers to the questions that fail ---------------------
# The owner's approval of 2026-11-23 ("I approve that plan perfect"): re-ask every question that has produced a not-right answer,
# three times each, on the shipped line-up, so that the caution fix meets enough fresh wrong answers to say what it catches.
# Measured beforehand: those 19 questions were not right on 23 of the 83 answers made to them (28 percent; 3.4 percent over all 681).
RERUN_REPEATS = int(os.environ.get("TALLY_RERUN_REPEATS", "3"))   # the revised caution fix's test (docs/preregistration-20261123-caution-v2-test.md): 3, and 1 for its control
RERUN_PER_ANSWER_CAP = 0.022    # as the tally's
RERUN_TIER4_PER_ANSWER_CAP = 0.030
RERUN_MIN_CAP = 0.10
RERUN_CEILING = 1.50            # the whole re-ask run, spend: the owner approved about '$0.8' and a cap of '$1.50'
# stage 1: every question with a not-right answer in the four labelled runs behind docs/reviews/2026-11-23-caution-flaw.md
RERUN_KNOWN = ([("professional-hard", q) for q in ("H4", "H8", "H12")] + [("professional", "P4")]
               + [("professional-holdout", q) for q in ("X12", "X13", "X16", "X19", "X20", "X31", "X34", "X38", "X41")]
               + [("professional-holdout-2", q) for q in ("Y68", "Y124", "Y140", "Y146", "Y149", "Y170")])


def rerun_out(stage: str) -> Path:
    return Path(os.environ.get("TALLY_RERUN_OUT", str(OUT))) / f"rerun{stage}"


def rerun_pairs(stage: str) -> list[tuple[str, str]]:
    """Stage 1 is the 19 known questions. Stage 2 is the questions whose tally answer was read not right: a JSON list of
    [set, id] in TALLY_RERUN_EXTRA, written after the reading and committed before the spend."""
    if stage == "1":
        return RERUN_KNOWN
    extra = json.loads(Path(os.environ["TALLY_RERUN_EXTRA"]).read_text(encoding="utf-8"))
    # TALLY_RERUN_KEEP_KNOWN=1: the revised fix's test asks the known questions again, on the tree that carries the revision.
    keep = os.environ.get("TALLY_RERUN_KEEP_KNOWN") == "1"
    return [(s, q) for s, q in extra if keep or (s, q) not in RERUN_KNOWN]


def rerun_lanes(stage: str) -> list[list[dict]]:
    """One invocation for each tally invocation that holds a chosen question, in the tally's own order and on the profile the
    question ran on there (the field questions on their own profile, never the small test)."""
    pairs = rerun_pairs(stage)
    out: list[list[dict]] = []
    for lane in lanes():
        for i in lane:
            if i["name"].startswith("E-"):
                continue
            ids = [q for q in i["ids"] if (i["set"], q) in pairs]
            if ids:
                per = RERUN_TIER4_PER_ANSWER_CAP if i["set"] == "tier4" else RERUN_PER_ANSWER_CAP
                cap = max(RERUN_MIN_CAP, round(len(ids) * RERUN_REPEATS * per, 2))
                out.append([dict(i, name=f"R{stage}-{i['name']}", ids=ids, cap=cap, repeats=RERUN_REPEATS)])
    found = {(i["set"], q) for lane in out for i in lane for q in i["ids"]}
    if set(pairs) - found:
        raise SystemExit(f"not in any tally invocation: {sorted(set(pairs) - found)}")
    return out


def rerun_plan(stage: str = "1") -> None:
    total, cap_sum = 0, 0.0
    for n, lane in enumerate(rerun_lanes(stage), 1):
        for i in lane:
            total += len(i["ids"]) * i["repeats"]
            cap_sum += i["cap"]
            print(f"lane {n:2d}: {i['name']} [{i['set']}, {i['profile']}] {len(i['ids'])} questions x {i['repeats']} = "
                  f"{len(i['ids']) * i['repeats']} answers, cap ${i['cap']:.2f}: {' '.join(i['ids'])}")
    print(f"stage {stage}: {len(rerun_pairs(stage))} questions, answers {total}, expected spend about ${total * 0.0135:.2f}, "
          f"sum of caps ${cap_sum:.2f}, ceiling for the whole re-ask run ${RERUN_CEILING:.2f}")


def rerun(stage: str = "1") -> None:
    out = rerun_out(stage)
    for n, lane in enumerate(rerun_lanes(stage), 1):
        script = write_lane(n, lane, out)
        subprocess.Popen(["bash", str(script)], start_new_session=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        print("started", script)


if __name__ == "__main__":
    MODES = {"plan": plan, "probe": probe, "run": run, "resume-plan": resume_plan, "resume": resume,
             "rerun-plan": lambda: rerun_plan(*sys.argv[2:3]), "rerun": lambda: rerun(*sys.argv[2:3])}
    MODES[sys.argv[1]]()
