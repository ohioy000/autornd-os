"""The final tally's lanes (docs/preregistration-20261123-final-tally.md): plan them, probe them, start them.

    python -I docs/probes/final_tally_launch.py plan            # free: prints the lanes, their questions and caps
    python -I docs/probes/final_tally_launch.py probe           # paid, '$0.10' a set: one question of tier2, golden, tier4
    python -I docs/probes/final_tally_launch.py run             # paid: starts every lane, detached, and returns

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
    return (f"{env} {PY} {TREE}/docs/probes/short_workflows_measurement.py {out}/{i['name']} 0 1 1 {i['cap']} "
            f"{' '.join(i['ids'])} > {out}/{i['name']}.log 2>&1")


def write_lane(n: int, lane: list[dict]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lanes").mkdir(exist_ok=True)
    path = OUT / "lanes" / f"lane{n:02d}.sh"
    lines = ["#!/bin/bash", f"cd {TREE}"]
    for i in lane:
        lines += [f'echo "START {i["name"]} $(date -u +%T)" >> {OUT}/status.txt', command(i, OUT),
                  f'echo "EXIT {i["name"]} $? $(date -u +%T)" >> {OUT}/status.txt']
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


if __name__ == "__main__":
    {"plan": plan, "probe": probe, "run": run}[sys.argv[1]]()
