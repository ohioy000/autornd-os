"""The frontier model's hold-out answers, cut as the preregistration says. Free.

    python -I docs/probes/frontier_holdout_analysis.py ANSWERS_JSONL CODES_JSON \
        "VERDICTS_GLOB" [SECOND_READING_JSON]

ANSWERS_JSONL is the file frontier_direct_probe.py wrote (FRONTIER_SET=
professional-holdout). CODES_JSON is the file blind_reading_packets.py kept
back from the readers. VERDICTS_GLOB matches the blind readers' files, each
code -> {"verdict": right | wrong, "outside_wrong": bool, ...}. The optional
SECOND_READING_JSON is the executor's reading, code -> {"verdict": ...}; where
it is given it overrides the blind verdict and the difference is printed.

It prints: right of 42 on the key rule and on the stricter rule that counts
a wrong claim outside the key; the cuts of docs/preregistration-20261118-
frontier-direct-holdout.md (the 26 and the 16, the five traps and the other
37, the three groups); cost and seconds an answer; the answers that name a
page; the answers whose text says a figure is unchecked (a keyword screen,
read by hand afterwards); the bars; and the harness's figures beside them.
The harness's figures are the hold-out run's, typed here from
docs/reviews/2026-11-17-holdout-run.md and not recomputed.
"""
from __future__ import annotations

import glob
import json
import re
import statistics
import sys
from pathlib import Path

answers = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]
codes = json.loads(Path(sys.argv[2]).read_text())
verdicts: dict = {}
for path in sorted(glob.glob(sys.argv[3])):
    verdicts.update(json.loads(Path(path).read_text()))
second = (json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv) > 4 else {})
second = {k: v for k, v in second.items() if isinstance(v, dict)}

READABLE = {"X1", "X2", "X4", "X5", "X6", "X7", "X8", "X9", "X10", "X11", "X13",
            "X14", "X15", "X16", "X21", "X22", "X23", "X24", "X25", "X27", "X28",
            "X34", "X36", "X37", "X39", "X42"}
TRAPS = {"X13", "X16", "X19", "X36", "X41"}
GROUPS = {"X1 to X14": range(1, 15), "X15 to X28": range(15, 29),
          "X29 to X42": range(29, 43)}
# The harness, as reported (docs/reviews/2026-11-17-holdout-run.md).
HARNESS = {"right": 113, "made": 126, "cost": 0.0108, "seconds": 107,
           "readable": (74, 78), "unreadable": (39, 48), "traps": (10, 15),
           "other": (103, 111), "stricter": 97,
           "groups": {"X1 to X14": (39, 42), "X15 to X28": (38, 42),
                      "X29 to X42": (36, 42)}}

by_question = {}
for code, meta in codes.items():
    if meta.get("delivered"):
        by_question[meta["question"]] = code
row = {a["id"]: a for a in answers}
missing = [q for q in (f"X{i}" for i in range(1, 43)) if q not in by_question
           or by_question[q] not in verdicts]
if missing:
    sys.exit(f"no verdict for {missing}")

final = {}
differ = []
for q, code in by_question.items():
    blind = verdicts[code]["verdict"]
    mine = second.get(code, {}).get("verdict")
    if mine and mine != blind:
        differ.append((q, blind, mine))
    final[q] = mine or blind
outside = {q for q, code in by_question.items()
           if verdicts[code].get("outside_wrong")}


def right_of(ids) -> tuple[int, int]:
    ids = list(ids)
    return sum(final[q] == "right" for q in ids), len(ids)


def line(name: str, got: tuple[int, int], harness: tuple[int, int] | None = None):
    text = f"{name:<34} {got[0]:>3} of {got[1]:<3} ({100 * got[0] / got[1]:.1f}%)"
    if harness:
        text += f"   harness {harness[0]} of {harness[1]} ({100 * harness[0] / harness[1]:.1f}%)"
    print(text)


allq = [f"X{i}" for i in range(1, 43)]
print("== right on the key rule ==")
line("all 42", right_of(allq), (HARNESS["right"], HARNESS["made"]))
strict = right_of([q for q in allq if q not in outside])
line("stricter (outside_wrong counts)", strict, (HARNESS["stricter"], HARNESS["made"]))
line("the 26 the harness's fetch reads", right_of(READABLE), HARNESS["readable"])
line("the 16 it cannot read", right_of(set(allq) - READABLE), HARNESS["unreadable"])
line("the 5 traps", right_of(TRAPS), HARNESS["traps"])
line("the other 37", right_of(set(allq) - TRAPS), HARNESS["other"])
for name, span in GROUPS.items():
    line(f"group {name}", right_of([f"X{i}" for i in span]), HARNESS["groups"][name])
wrong = sorted((q for q in allq if final[q] != "right"), key=lambda q: int(q[1:]))
print("wrong:", wrong)
print("blind and second reading differ:", differ or "none")
print("outside_wrong marks on right answers:",
      sorted(q for q in outside if final[q] == "right"))

print("\n== cost and time ==")
costs = [row[q]["cost"] for q in allq]
secs = [row[q]["seconds"] for q in allq]
print(f"total ${sum(costs):.4f}  mean ${statistics.mean(costs):.4f}  "
      f"median ${statistics.median(costs):.4f}  max ${max(costs):.4f}")
print(f"seconds mean {statistics.mean(secs):.1f}  median {statistics.median(secs):.1f}  "
      f"max {max(secs):.1f}   (harness: ${HARNESS['cost']} and {HARNESS['seconds']} s)")
print(f"harness cost / frontier cost = {HARNESS['cost'] / statistics.mean(costs):.3f}")
print("dearest:", sorted(((row[q]['cost'], q) for q in allq), reverse=True)[:4])

print("\n== what the answers show ==")
URL = re.compile(r"https?://|\b[a-z0-9-]+\.(?:gov|org|eu|int|com|nz|au|uk|ca)\b", re.I)
cited = [q for q in allq if row[q].get("citations")]
named = [q for q in allq if row[q].get("citations") or URL.search(row[q]["answer"])]
print(f"carry a citation annotation: {len(cited)} of 42; name a page by citation or in the text: {len(named)}")
DOUBT = re.compile(
    r"(could not|couldn't|can't|cannot|unable to|not able to|did not|didn't|wasn't able)"
    r"[^.\n]{0,60}(verify|confirm|access|open|retriev|fetch|find|locate|read)|"
    r"should (?:be )?(?:verif|check|confirm)|double-check|recommend (?:verif|check|confirm)|"
    r"not (?:independently )?verified|unverified|from memory|my recollection|"
    r"worth (?:verif|check|confirm)", re.I)
flagged = {}
for q in allq:
    hits = [m.group(0) for m in DOUBT.finditer(row[q]["answer"])]
    if hits:
        flagged[q] = hits[:2]
print(f"keyword screen says a figure is unchecked or to be verified: {len(flagged)} of 42 "
      f"(a screen; the hits are read by hand)")
print("  of the wrong answers:", [q for q in wrong if q in flagged], "of", wrong)
for q, hits in flagged.items():
    print(f"  {q} [{final[q]}] {hits}")
if second:
    by_hand = {q for q, code in by_question.items()
               if second.get(code, {}).get("says_unchecked")}
    check = {q for q, code in by_question.items()
             if second.get(code, {}).get("check_current_page")}
    hedged = {q for q, code in by_question.items()
              if second.get(code, {}).get("hedged_key_item")}
    print(f"read by hand: {len(by_hand)} of 42 say a figure they give is unconfirmed, from "
          f"memory or to be checked: {sorted(by_hand, key=lambda q: int(q[1:]))}")
    print(f"  the screen caught {len(by_hand & set(flagged))} of them; "
          f"{len(check)} more say to check a current page for a later change: {sorted(check)}")
    print(f"  key item given only in hedged words: {sorted(hedged)}; counted wrong, "
          f"right would be {42 - len(hedged & set(allq))} of 42")

print("\n== the bars ==")
rate = right_of(allq)[0] / 42
print(f"1. harness {100 * HARNESS['right'] / HARNESS['made']:.1f}% against frontier "
      f"{100 * rate:.1f}%: gap {100 * rate - 100 * HARNESS['right'] / HARNESS['made']:+.1f} points "
      f"-> {'met' if 100 * rate - 100 * HARNESS['right'] / HARNESS['made'] <= 5 else 'MISSED'} "
      f"(met at 39 or fewer right of 42)")
ratio = HARNESS["cost"] / statistics.mean(costs)
print(f"2. harness cost is {ratio:.3f} of the frontier's -> "
      f"{'met' if ratio <= 0.25 else 'MISSED'} (met at a quarter or less)")
