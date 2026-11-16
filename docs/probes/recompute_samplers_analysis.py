"""Read the sampler test's units. Free.

    python -I docs/probes/recompute_samplers_analysis.py REPO OUT_DIR [QUESTION_ID]

OUT_DIR holds the probe's shard-N.jsonl (docs/probes/recompute_samplers_probe.py).
For each model it counts, over the completed units: the samples that hold
the key's figure (a pointer; the samples are read by hand), the vote it
would have given on the answer as delivered, and the vote it would have
given had the answer stated the commonly confused figure in the key
figure's place. With a QUESTION_ID it prints that question's units, every
sample's values beside the answer's. With ANY_SHAPE=1 in the environment the
samples are first read whatever key their values sit under (`any_shape`),
and every vote is worked out again from them.

CONFUSED was written before any sample was read: for each question, the
key's leading figure and the figure the question is commonly answered with.
"""
from __future__ import annotations

import copy
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
ONLY = sys.argv[3] if len(sys.argv) > 3 else None
sys.path.insert(0, str(REPO))
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION",
             "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"
os.chdir("/")  # no .env here, so only the placeholders are read

from autornd.graph import checks  # noqa: E402

# question: (the key's leading figure, the commonly confused figure)
CONFUSED = {
    "M1": ("12500", "6000"), "M2": ("9", "12"), "M3": ("10", "11"),
    "M4": ("4", "6"), "M5": ("9", "10"), "M6": ("20", "30"),
    "M7": ("9113", "7540"), "M8": ("8996", "7525"), "M9": ("12.71", "12.21"),
    "M10": ("184500", "176100"), "M11": ("150", "100"),
    "M12": ("24500", "23500"), "H1": ("10", "9"),
}
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def figures(value: object) -> list[str]:
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        return [f"{value:g}"]
    return [f"{float(n.replace(',', '')):g}" for n in NUMBER.findall(str(value))]


def confused_answer(results: list, key: str, other: str) -> list | None:
    """The delivered results with the key's figure replaced by the confused
    one, in the first result that states it; None when no result states it."""
    out = copy.deepcopy(results or [])
    for result in out:
        if not isinstance(result, dict):
            continue
        value = result.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if f"{value:g}" == f"{float(key):g}":
                result["value"] = float(other)
                return out
        elif isinstance(value, str) and f"{float(key):g}" in figures(value):
            result["value"] = re.sub(
                NUMBER, lambda m: other if f"{float(m.group().replace(',', '')):g}"
                == f"{float(key):g}" else m.group(), value, count=0)
            return out
    return None


def any_shape(sample: object) -> object:
    """A sample with its values under `results`, whatever key the model put
    them under. Two of the first batch's models answered under "answers" or
    "asks", or as one bare result; the harness reads none of those. This is
    for the reading that tells a model that does not know the figure from
    one that does not follow the reply's shape. It is not the harness."""
    if not isinstance(sample, dict) or sample.get("failed"):
        return sample
    if isinstance(sample.get("results"), list):
        return sample
    if "ask" in sample and "value" in sample:
        return {"results": [sample]}
    for value in sample.values():
        if isinstance(value, list) and value and all(
                isinstance(v, dict) and "value" in v for v in value):
            return {"results": value}
    return sample


TOLERANT = os.environ.get("ANY_SHAPE") == "1"
units = [json.loads(line) for path in sorted(glob.glob(str(OUT / "shard-*.jsonl")))
         for line in open(path, encoding="utf-8")]
totals: dict[str, Counter] = defaultdict(Counter)
for unit in units:
    if unit.get("status") != "completed" or not unit.get("models"):
        totals["(units)"][f"status:{unit.get('status')}"] += 1
        continue
    totals["(units)"]["completed"] += 1
    key, other = CONFUSED[unit["question"]]
    answer_holds_key = any(f"{float(key):g}" in figures(r.get("value"))
                           for r in unit.get("results") or [] if isinstance(r, dict))
    swapped = confused_answer(unit.get("results"), key, other)
    if ONLY == unit["question"]:
        print(f"\n## {unit['question']} r{unit['repeat']} answer "
              f"{[(r.get('ask'), r.get('value'), r.get('unit')) for r in unit.get('results') or []]}"[:400])
    for model, entry in unit["models"].items():
        total = totals[model]
        total["units"] += 1
        total["cost"] += float(entry.get("cost") or 0.0)
        total["seconds"] += float(entry.get("seconds") or 0.0)
        samples = entry.get("samples") or []
        total["samples_in_the_shape_asked"] += sum(
            1 for x in samples if isinstance(x, dict)
            and isinstance(x.get("results"), list))
        vote = entry.get("vote") or {}
        if TOLERANT:
            samples = [any_shape(x) for x in samples]
            vote = checks.recompute_vote(unit.get("results") or [], samples,
                                         unit.get("asks") or [], "").data
        for sample in samples:
            total["samples"] += 1
            if not isinstance(sample, dict) or sample.get("failed"):
                total["samples_failed"] += 1
                continue
            stated = [f for r in sample.get("results") or [] if isinstance(r, dict)
                      for f in figures(r.get("value"))]
            total["samples_with_key_figure"] += f"{float(key):g}" in stated
            total["samples_with_confused_figure"] += (
                f"{float(other):g}" in stated and f"{float(key):g}" not in stated)
        total["flags_as_delivered"] += bool(vote.get("flagged"))
        total["flags_where_answer_holds_key"] += bool(vote.get("flagged")) and answer_holds_key
        total["answers_holding_key"] += answer_holds_key
        total["compared_nothing"] += bool(vote.get("unchecked")) or not vote.get("checked", True)
        if swapped is not None:
            total["confused_cases"] += 1
            would = checks.recompute_vote(swapped, samples, unit.get("asks") or [],
                                          "").data
            total["confused_flagged"] += bool(would.get("flagged"))
            total["confused_compared_nothing"] += (
                bool(would.get("unchecked")) or not would.get("checked", True))
        if ONLY == unit["question"]:
            print(f"   {model[:34]:34} flagged={vote.get('flagged')} "
                  f"unchecked={vote.get('unchecked')} ${entry.get('cost')} "
                  f"{entry.get('seconds')}s {entry.get('error', '')}")
            for sample in samples:
                print("        ", str([(r.get("ask"), r.get("value"), r.get("unit"))
                                       for r in (sample.get("results") or [])
                                       if isinstance(r, dict)]
                                      if isinstance(sample, dict) else sample)[:260])
if ONLY is None:
    for model, total in totals.items():
        total["cost"] = round(total["cost"], 4)
        total["seconds"] = round(total["seconds"])
        print(model, dict(total))
