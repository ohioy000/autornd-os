"""The eleven-question rerun, read as preregistered. Free.

    python -I docs/probes/eleven_rerun_analysis.py HARNESS_GLOB FRONTIER_GLOB \
        CODES_JSON "VERDICTS_GLOB" [SECOND_READING_JSON]

HARNESS_GLOB matches the harness arm's records (short_workflows_measurement.py
shard files, and any redo file written beside them). FRONTIER_GLOB matches the
frontier arm's passes (frontier_direct_probe.py output files). CODES_JSON is
the file blind_reading_packets.py kept back from the readers; an answer whose
source path holds "pass" is the frontier arm's, any other the harness's.
VERDICTS_GLOB matches the blind readers' files (code -> {"verdict",
"outside_wrong", ...}). The optional SECOND_READING_JSON is the executor's
reading, code -> {"verdict": ...}; where given it overrides the blind verdict
and every difference is printed.

A harness unit that ended on a provider 402 (credit) never made an answer; it
is listed and left out of "made", as the preregistration of 2026-11-19 and the
hold-out run's rule for answers blocked by the network have it. A unit blocked
by the harness's own checks counts as made and not right. A frontier call that
failed is the same: listed, left out.

It prints, for each arm, the answers right of those made, by question and
draw, the cost and seconds an answer, and the four bars of
docs/preregistration-20261119-eleven-rerun.md with its addenda.
"""
from __future__ import annotations

import collections
import glob
import json
import re
import statistics
import sys
from pathlib import Path

ELEVEN = ["X3", "X12", "X13", "X16", "X19", "X20", "X24", "X31", "X34", "X38", "X41"]
FIRST_RUN = {"harness_right": 20, "harness_made": 33, "frontier_medium_right": 11}


def lines(pattern: str) -> list[tuple[str, int, dict]]:
    out = []
    for path in sorted(glob.glob(pattern)):
        if "phases" in path or path.endswith(".log"):
            continue
        for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
            if line.strip():
                out.append((path, n, json.loads(line)))
    return out


harness = [(p, n, r) for p, n, r in lines(sys.argv[1]) if r.get("status") != "not_started"]
frontier = lines(sys.argv[2])
codes = json.loads(Path(sys.argv[3]).read_text())
blind: dict = {}
for path in sorted(glob.glob(sys.argv[4])):
    blind.update(json.loads(Path(path).read_text()))
second = json.loads(Path(sys.argv[5]).read_text()) if len(sys.argv) > 5 else {}
second = {k: v for k, v in second.items() if isinstance(v, dict)}

verdict_of: dict[str, str] = {}
differ = []
for code in codes:
    if code in blind:
        mine = second.get(code, {}).get("verdict")
        if mine and mine != blind[code]["verdict"]:
            differ.append((code, blind[code]["verdict"], mine))
        verdict_of[code] = mine or blind[code]["verdict"]


def where(path: str, n: int) -> str:
    """'shard-0#4' or 'pass2#5': the file's own name without the folder or the
    trace prefix, so a codes file kept with its paths from the day of the run
    still joins to the same records copied into docs/traces/."""
    return f"{re.search(r'(shard-\d+|pass\d)\.jsonl', path).group(1)}#{n}"


by_source = {}
for code, meta in codes.items():
    file, _, n = meta["source"].partition("#")
    by_source[where(file, int(n))] = code


def is_402(record: dict) -> bool:
    return "402" in str(record.get("error") or "")


def draw_of(path: str, n: int, record: dict, arm: str) -> int:
    if arm == "harness":
        return record["repeat"]
    return int(re.search(r"pass(\d)\.jsonl", path).group(1))


def outcome(arm: str, path: str, n: int, record: dict) -> str | None:
    """right | wrong | blocked, or None for a unit that made no answer (402)."""
    if arm == "harness":
        if is_402(record):
            return None
        if not record.get("delivered"):
            return "blocked"
    else:
        if record.get("status") != "answered":
            return None
    code = by_source.get(where(path, n))
    if code is None or code not in verdict_of:
        sys.exit(f"no verdict for {path}#{n}")
    return verdict_of[code]


table: dict[str, dict[str, dict[int, str]]] = {"harness": {}, "frontier": {}}
costs = {"harness": [], "frontier": []}
seconds = {"harness": [], "frontier": []}
not_made = {"harness": [], "frontier": []}
for arm, rows in (("harness", harness), ("frontier", frontier)):
    for path, n, record in rows:
        q = record["question"] if arm == "harness" else record["id"]
        draw = draw_of(path, n, record, arm)
        result = outcome(arm, path, n, record)
        if result is None:
            not_made[arm].append((q, draw))
            continue
        # a later attempt of the same (question, draw) replaces an earlier 402
        table[arm].setdefault(q, {})[draw] = result
        cost = float(record.get("cost") or 0.0) + float(record.get("liability") or 0.0)
        costs[arm].append(cost)
        seconds[arm].append(float(record.get("seconds") or 0.0))
# a 402 that was made again is no longer missing
for arm in not_made:
    not_made[arm] = [(q, d) for q, d in not_made[arm] if d not in table[arm].get(q, {})]


def totals(arm: str) -> tuple[int, int]:
    made = sum(len(v) for v in table[arm].values())
    right = sum(1 for v in table[arm].values() for x in v.values() if x == "right")
    return right, made


print("== by question and draw (R right, W wrong, B blocked by its own checks, - not made) ==")
print(f"{'':5}{'harness 1 2 3':<18}{'frontier 1 2 3':<18}")
for q in ELEVEN:
    def cells(arm: str) -> str:
        return " ".join({"right": "R", "wrong": "W", "blocked": "B"}.get(
            table[arm].get(q, {}).get(d, ""), "-") for d in (1, 2, 3))
    print(f"{q:<5}{cells('harness'):<18}{cells('frontier'):<18}")
print("not made (a provider 402, never an answer): harness",
      sorted(set(not_made["harness"])), "| frontier", sorted(set(not_made["frontier"])))
print("blind and second reading differ:", differ or "none")

hr, hm = totals("harness")
fr, fm = totals("frontier")
print("\n== right of made ==")
print(f"harness  {hr} of {hm} ({100 * hr / hm:.1f}%)   first run on these 11: "
      f"{FIRST_RUN['harness_right']} of {FIRST_RUN['harness_made']} (60.6%)")
print(f"frontier {fr} of {fm} ({100 * fr / fm:.1f}%)   first draw at medium: "
      f"{FIRST_RUN['frontier_medium_right']} of 11")
per_q_miss = collections.Counter(q for q, d in table["harness"].items()
                                 for x in d.values() if x != "right")
print("harness questions not right in 0, 1, 2, 3 draws:",
      [len(ELEVEN) - len(per_q_miss)] + [sum(1 for c in per_q_miss.values() if c == k) for k in (1, 2, 3)])

print("\n== cost and time an answer ==")
for arm in ("harness", "frontier"):
    print(f"{arm:<9} cost mean ${statistics.mean(costs[arm]):.4f} (median "
          f"${statistics.median(costs[arm]):.4f}, total ${sum(costs[arm]):.3f}), "
          f"seconds mean {statistics.mean(seconds[arm]):.1f}")

print("\n== the bars ==")
print(f"1. harness right {hr} of {hm} ({100 * hr / hm:.1f}%); bar: at least 27 of 33 "
      f"(82%): {'met' if 100 * hr / hm >= 81.8 else 'not met'}"
      f"{' (zone 24-26 of 33: partly)' if 72.7 <= 100 * hr / hm < 81.8 else ''}")
print(f"2. frontier right {fr} of {fm} ({100 * fr / fm:.1f}%); bar: at least 91%: "
      f"{'met' if 100 * fr / fm >= 90.9 else 'not met'}")
gap = 100 * fr / fm - 100 * hr / hm
print(f"3. frontier minus harness = {gap:+.1f} points; bar: within 5: "
      f"{'met' if gap <= 5 else 'not met'}")
ratio = statistics.mean(costs["harness"]) / statistics.mean(costs["frontier"])
print(f"4. harness cost is {ratio:.3f} of the frontier's; bar: a quarter or less: "
      f"{'met' if ratio <= 0.25 else 'not met'}")
