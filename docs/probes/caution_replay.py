"""What the delivery's cautions say beside the labelled answers of four runs, with and without the gaps. Free.

    python -I docs/probes/caution_replay.py REPO TRACES_DIR [TRACES_DIR ...]

REPO is the tree whose code is replayed (it is put first on sys.path, so `autornd.api.routes` is that tree's).
TRACES_DIR holds the committed traces: each run's shards, its phase rows (`...-phases-shard-N.jsonl`), and its reading
files (`...-reading-codes.json`, the blind readers' `...-reading-blind-verdicts-*.json` and the executor's
`...-reading-second-reading.json`); give every directory the files are in. A run whose files are not found is skipped
and said.

The cautions are rebuilt from the stored phase rows exactly as `_detail` builds them, and each rebuild is compared with
the cautions the run recorded (a rebuild that does not match stops the script, as `holdout2_analysis.py` does); the gaps
(`routes._gaps`) are then read off the same rows. Nothing is run, nothing is paid for, no model is called.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
DIRS = [Path(p).resolve() for p in sys.argv[2:]]
sys.path.insert(0, str(REPO))
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION", "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"

from autornd.api import routes  # noqa: E402
from autornd.graph import checks  # noqa: E402

# name -> (the reading files' common prefix, the prefix its shards are named by when the code's source is an arm directory)
RUNS = {
    "holdout-1 (2026-11-17)": ("20261117T-holdout", None),
    "acceptance (2026-11-17)": ("20261117T-acceptance", None),
    "eleven-question rerun (2026-11-19)": ("20261119T-eleven-rerun", None),
    "holdout-2 (2026-11-22)": ("20261122T-holdout2", "20261122T-holdout2-{arm}"),
    "holdout-2 unpinned arm (2026-11-22)": ("20261122T-holdout2-unpinned", "20261122T-holdout2-{arm}"),
}


def find(name: str) -> Path | None:
    for d in DIRS:
        if (d / name).exists():
            return d / name
    return None


def stem_of(source: str, arm_pattern: str | None) -> tuple[str, str, int]:
    """The traces' name stem, the shard's file name and the unit's line, from a code's recorded source.

    A source is `evals/results/<run>/<shard>#<line>` or, for a run made of arms, `evals/results/<run>/<arm>/<shard>#<line>`;
    the committed trace of an arm is `<run>-<arm>-<shard>` (the acceptance run's redo arms), except the second hold-out
    run's, which dropped its run name's tail (`20261122T-holdout2-{arm}`, said by `arm_pattern`)."""
    path, n = source.rsplit("#", 1)
    p = Path(path)
    arm, run = p.parent.name, p.parent.parent.name
    if arm == "eleven-rerun":
        return "20261119T-eleven-rerun", p.name, int(n)
    if arm_pattern and not arm.startswith("2026"):
        return arm_pattern.format(arm=arm), p.name, int(n)
    if run.startswith("2026") and not arm.startswith("2026"):
        return f"{run}-{arm}", p.name, int(n)
    return arm, p.name, int(n)


def last(verdicts, name):
    return next((v for n, v in reversed(verdicts) if n == name and isinstance(v, dict)), None)


def shipped(verdicts):
    """The cautions `_detail` builds from these rows, before the gaps: the same calls, in the same order."""
    answer = (last(verdicts, "implement") or {}).get("summary")
    vote = next((v for n, v in reversed(verdicts) if n == "recompute_vote"), None)
    sources = [v for n, v in verdicts if n == "sources"]
    vote = routes._settled(verdicts, vote, sources)
    results = (last(verdicts, "implement") or {}).get("results")
    differing = routes._differing(sources)
    backed, unconfirmed = routes._checked_figures(results, sources, differing)
    if vote is not None and backed:
        vote = dict(vote, backed_by_source=backed)
    asked = len((last(verdicts, "asks") or {}).get("asks") or [])
    return routes._cautions(vote, sources, answer is not None, asked, unconfirmed, differing,
                            calculation=routes._judged_a_calculation(verdicts))


def load(name: str, prefix: str, arm_pattern: str | None):
    codes_path = find(f"{prefix}-reading-codes.json")
    if codes_path is None:
        print(f"SKIPPED {name}: no {prefix}-reading-codes.json in the directories given")
        return []
    codes = json.loads(codes_path.read_text())
    verdicts: dict = {}
    for d in DIRS:
        for f in sorted(glob.glob(str(d / f"{prefix}-reading-blind-verdicts-*.json"))):
            if prefix.endswith("holdout2") and "unpinned" in f:
                continue
            data = json.loads(Path(f).read_text())
            verdicts.update({k: v for k, v in data.items() if isinstance(v, dict) and "verdict" in v})
    second_path = find(f"{prefix}-reading-second-reading.json")
    second = {}
    if second_path is not None:
        data = json.loads(second_path.read_text())
        second = {k: v for k, v in data.items() if isinstance(v, dict) and "verdict" in v}
    out, cache, frontier = [], {}, 0
    for code, meta in codes.items():
        if not meta.get("delivered"):
            continue
        if Path(meta["source"].rsplit("#", 1)[0]).parent.name == "eleven-frontier":
            frontier += 1  # a frontier model's own answer: no harness run behind it, so no delivery to caution
            continue
        stem, shard, n = stem_of(meta["source"], arm_pattern)
        shard_p, phases_p = find(f"{stem}-{shard}"), find(f"{stem}-phases-{shard}")
        if shard_p is None or phases_p is None:
            print(f"SKIPPED {name} {meta['question']}: {stem}-{shard} not found")
            continue
        if phases_p not in cache:
            cache[phases_p] = [json.loads(x) for x in open(phases_p, encoding="utf-8")]
            cache[shard_p] = [json.loads(x) for x in open(shard_p, encoding="utf-8")]
        rows = cache[phases_p]
        workflow = [r for r in rows if r["kind"] == "workflow"][n]
        phases = sorted((r for r in rows if r["kind"] == "phase" and r["workflow_id"] == workflow["id"]),
                        key=lambda r: r["created_at"])
        unit = cache[shard_p][n]
        out.append({"run": name, "code": code, "q": meta["question"],
                    "label": (second.get(code) or verdicts.get(code) or {}).get("verdict", "MISSING"),
                    "verdicts": [(r["phase"], json.loads(json.dumps(r["verdict"]))) for r in phases],
                    "request": workflow["request"], "recorded": unit.get("cautions") or []})
    if frontier:
        print(f"LEFT OUT {name}: {frontier} answers of a frontier model (no harness run, so no cautions)")
    return out


KINDS = (("no_result", "gives no result for ask"), ("blocked", "could not answer"),
         ("not_stated", "is not stated in the document"), ("short_text", "word"))


def kind(caution: str) -> str:
    return next((k for k, text in KINDS if text in caution), "other")


pool: list[dict] = []
for name, (prefix, arm_pattern) in RUNS.items():
    pool += load(name, prefix, arm_pattern)
for u in pool:
    u["old"] = shipped(u["verdicts"])
    if u["recorded"] != u["old"]:
        raise SystemExit(f"{u['run']} {u['q']} {u['code']}: the rebuilt cautions are not the recorded ones")
    u["gaps"] = routes._gaps(u["verdicts"], u["request"])
right = [u for u in pool if u["label"] == "right"]
not_right = [u for u in pool if u["label"] != "right"]
print(f"labelled delivered answers: {len(pool)}  right {len(right)}  not right {len(not_right)}  "
      f"unread {sum(u['label'] == 'MISSING' for u in pool)}")
print(f"  the not-right ones by the two readers' verdict: {dict(Counter(u['label'] for u in not_right))}")
for name in RUNS:
    mine = [u for u in pool if u["run"] == name]
    if mine:
        print(f"  {name}: {len(mine)} answers, {sum(u['label'] != 'right' for u in mine)} not right")


def share(group, key):
    hit = sum(1 for u in group if key(u))
    return f"{hit} of {len(group)} ({100 * hit / len(group):.1f}%)" if group else "none"


print()
print("                                  right answers              not-right answers")
for label, key in (("a caution as shipped", lambda u: bool(u["old"])),
                   ("a gap caution (new)", lambda u: bool(u["gaps"])),
                   ("either", lambda u: bool(u["old"] or u["gaps"])),
                   ("neither (comes clean)", lambda u: not (u["old"] or u["gaps"]))):
    print(f"  {label:26s} {share(right, key):26s} {share(not_right, key)}")
by_right = Counter(k for u in right for k in {kind(g) for g in u["gaps"]})
by_wrong = Counter(k for u in not_right for k in {kind(g) for g in u["gaps"]})
print("\ngap cautions by kind (answers carrying one):")
for k, _ in KINDS:
    print(f"  {k:12s} right {by_right[k]:3d}   not right {by_wrong[k]:3d}")
print("\nEVERY ANSWER NOT RIGHT:")
for u in not_right:
    print(f"  {u['run'][:22]:22s} {u['q']:5s} {u['code']} {u['label']:6s} shipped cautions {len(u['old'])}"
          f"  gaps: {[g[:90] for g in u['gaps']]}")
print("\nEVERY RIGHT ANSWER THAT GETS A GAP:")
for u in right:
    if u["gaps"]:
        print(f"  {u['run'][:22]:22s} {u['q']:5s} {u['code']} gaps: {[g[:90] for g in u['gaps']]}")


# ---- What else was measured, so the review's other figures can be reproduced -------------------------------------
SHIPPED_KINDS = (("a figure on no page", "is in none of the passages"),
                 ("two pages give different figures", "different figures"),
                 ("the vote did not run, compared nothing or had no majority", ("did not run", "compared nothing", "no majority")),
                 ("any caution of the vote", ("worded ask", "vote disagrees", "did not run", "compared nothing", "no majority",
                                              "could not compare")),
                 ("the lookup ran and nothing was read, or none ran", ("No lookup ran", "A lookup ran, but")))


def carries(texts, needles):
    needles = (needles,) if isinstance(needles, str) else needles
    return any(any(n in t for n in needles) for t in texts)


print("\nSHIPPED CAUTIONS BY KIND (answers carrying one; an answer can carry several):")
for label, needles in SHIPPED_KINDS:
    print(f"  {label:60s} {share(right, lambda u: carries(u['old'], needles)):24s} {share(not_right, lambda u: carries(u['old'], needles))}")


def last_of(u, name):
    return last(u["verdicts"], name) or {}


def free_checks(u):
    """The two free checks that run beside every answer and whose findings the delivery throws away."""
    proposals = last_of(u, "asks").get("asks") or []
    text = last_of(u, "implement").get("summary") or ""
    anchored = checks.asks_anchored(proposals, u["request"])
    coverage = checks.criteria_addressed(anchored.data["quotes"], text, fallback=anchored.data["fallback"])
    consistency = checks.numbers_consistent(u["request"], text)
    return (not coverage.passed and coverage.data.get("checked", True) is not False), not consistency.passed


for u in pool:
    u["coverage_missed"], u["numbers_conflict"] = free_checks(u)
    u["silent"] = not (u["old"] or u["gaps"])
print("\nTHE TWO FREE CHECKS THE DELIVERY NEVER SURFACES (criteria_addressed, numbers_consistent):")
for label, key in (("criteria_addressed finds an ask missing", "coverage_missed"), ("numbers_consistent finds a conflict", "numbers_conflict")):
    marked = [(u["q"], u["code"], "comes clean" if u["silent"] else "has a caution") for u in not_right if u[key]]
    print(f"  {label:42s} {share(right, lambda u: u[key]):24s} {share(not_right, lambda u: u[key])}  not right: {marked}")

# Analysis only: prose is never read for control flow in the harness. It is read here to say how many answers hedge in words.
HEDGE = re.compile(r"(could not (?:be )?(?:confirm|verif|establish|determin|read|fetch|locat|find)|cannot (?:be )?(?:confirm|verif|establish|determin)|"
                   r"unable to (?:confirm|verif|determin)|not (?:been )?(?:confirmed|verified|established)|unconfirmed|unverified|"
                   r"please (?:confirm|verify)|should (?:be )?(?:confirm|verif)|reviewer should|to be confirmed|"
                   r"needs? (?:to be )?(?:confirm|verif)|\binferred\b|not captured|"
                   r"no text .{0,40}(?:was|were) (?:captured|retrieved)|uncertain)", re.I)
print("\nHEDGING IN THE ANSWER'S OWN PROSE (analysis only; the harness never reads prose for control flow):")
print(f"  a hedging phrase present                                   {share(right, lambda u: HEDGE.search(last_of(u, 'implement').get('summary') or '')):24s} "
      f"{share(not_right, lambda u: HEDGE.search(last_of(u, 'implement').get('summary') or ''))}")

print("\nWORDS IN THE ANSWER TEXT:")
print(f"  shortest right answers: {sorted(len((last_of(u, 'implement').get('summary') or '').split()) for u in right)[:5]}   "
      f"shortest not-right answers: {sorted(len((last_of(u, 'implement').get('summary') or '').split()) for u in not_right)[:5]}")

ran = lambda u: bool((last(u["verdicts"], "recompute_vote") or {}) and not (last(u["verdicts"], "recompute_vote") or {}).get("skipped"))
flagged = lambda u: bool((last(u["verdicts"], "recompute_vote") or {}).get("flagged"))
print("\nTHE RECOMPUTE VOTE:")
print(f"  ran                                                        {share(right, ran):24s} {share(not_right, ran)}")
print(f"  flagged a disagreement                                     {share(right, flagged):24s} {share(not_right, flagged)}")

