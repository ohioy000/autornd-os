"""Re-score every recorded tier-2 answer in docs/traces under the
tier-2 scorer's frozen-2026-10-03.3 and frozen-2026-10-03.4, and
print every verdict that moves.

Provider-free and offline. Run from the repository root:

    .venv/bin/python3 docs/probes/tier2_scorer_v4_rescore.py

The .3 scorer is read from git at OLD_COMMIT (main before .4) and
checked against the sha256 versions.json records for it. The keys and
questions are the frozen ones both versions score against. The 58-entry
reading sheet of the 2026-10-05 tier-3 run lives in evals/results/,
which is git-ignored; when it is present its agreement is printed too.

Which answers are right comes from the readings, not from either
scorer: docs/reviews/2026-11-13-short-workflows-measurement.md read all
35 answers .3 failed in the 2026-11-13 tier-2 run as right, and
docs/reviews/2026-11-13-golden-decisions.md read all nine golden Q2, Q4
and Q5 answers of batch 1 as right. One reader read both; D50 asks for
two, so this is a stated departure.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER2 = ROOT / "evals" / "tier2"
TRACES = ROOT / "docs" / "traces"
SHEET = (ROOT / "evals" / "results"
         / "20261005T215237Z-tier3-run.reading-sheet.json")
OLD_COMMIT = "751fbaf"
OLD_SHA = "0466388629ce70d71816e4c6ab73083ebe1fba67cc5514adc5fdfe5e49cb287f"
READ_RIGHT_RUNS = ("20261113T091013Z", "20261113T180026Z")


def _load(name: str, directory: Path):
    spec = importlib.util.spec_from_file_location(
        name, directory / "scorer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _corpus() -> list[dict]:
    """Every recorded answer to a tier-2 question in the traces: the
    tier-3 run, the remeasure, the smokes, the 2026-11-13 tier-2 run,
    and golden batch 1's Q2, Q4 and Q5 (shards 0-2; Q6 and IA are not
    tier-2 questions)."""
    out = []
    for path in sorted(TRACES.glob("*.jsonl")):
        name = path.name
        if "phases" in name:
            continue
        if "golden-batch1" in name and not any(
                f"shard-{n}" in name for n in (0, 1, 2)):
            continue
        for line_no, line in enumerate(path.open(encoding="utf-8")):
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            question = record.get("question") or record.get("question_id")
            answer = record.get("answer")
            if (isinstance(question, str)
                    and re.fullmatch(r"Q\d{1,2}", question)
                    and isinstance(answer, str) and answer.strip()):
                shape = record.get("workflow") or record.get("arm")
                repeat = record.get("repeat") or record.get("repetition")
                out.append({"label": f"{name[:16]}:{line_no}:{question}:"
                                     f"{shape}:{repeat}",
                            "question": question, "answer": answer})
    return out


def _sheet() -> list[dict]:
    if not SHEET.exists():
        return []
    entries = json.loads(SHEET.read_text(encoding="utf-8"))["entries"]
    out = []
    for entry in entries:
        resolution = entry["resolution"]
        if isinstance(resolution, str):
            resolution = (ast.literal_eval(resolution)
                          if resolution != "None" else None)
        out.append({"label": f"sheet:{entry['entry']}",
                    "question": entry["question_id"],
                    "answer": entry["answer"],
                    "truth": resolution["verdict"] if resolution else None})
    return out


def _failed(scorer, unit: dict) -> tuple[str, list[str]]:
    result = scorer.score(unit["question"], unit["answer"])
    return result["verdict"], [i["item"] for i in result["items"]
                               if not i["pass"]]


def main() -> int:
    old_source = subprocess.run(
        ["git", "show", f"{OLD_COMMIT}:evals/tier2/scorer.py"],
        cwd=ROOT, capture_output=True, check=True).stdout
    assert hashlib.sha256(old_source).hexdigest() == OLD_SHA, (
        "the scorer at OLD_COMMIT is not frozen-2026-10-03.3")
    with tempfile.TemporaryDirectory() as tmp:
        old_dir = Path(tmp)
        for data in TIER2.glob("*.json"):
            shutil.copy(data, old_dir / data.name)
        (old_dir / "scorer.py").write_bytes(old_source)
        old = _load("scorer_v3", old_dir)
        new = _load("scorer_v4", TIER2)
        corpus = _corpus()
        before = {u["label"]: _failed(old, u) for u in corpus}
        after = {u["label"]: _failed(new, u) for u in corpus}
        sheet = _sheet()
        sheet_old = {u["label"]: _failed(old, u)[0] for u in sheet}
        sheet_new = {u["label"]: _failed(new, u)[0] for u in sheet}

    def passes(scored: dict) -> int:
        return sum(v[0] == "PASS" for v in scored.values())

    print(f"Recorded tier-2 answers in docs/traces: {len(corpus)}")
    print(f"  PASS under frozen-2026-10-03.3: {passes(before)}")
    print(f"  PASS under frozen-2026-10-03.4: {passes(after)}")
    read_right = [label for label, (verdict, _) in before.items()
                  if verdict != "PASS"
                  and label.startswith(READ_RIGHT_RUNS)]
    fixed = [label for label in read_right if after[label][0] == "PASS"]
    print(f"Read right and failed by .3: {len(read_right)}; "
          f"passed by .4: {len(fixed)}")
    for label in read_right:
        if after[label][0] != "PASS":
            print(f"  still failed: {label} {after[label][1]}")
    new_fails = [label for label in corpus_labels(corpus)
                 if set(after[label][1]) - set(before[label][1])]
    print(f"Answers with an item .4 fails that .3 passed: {len(new_fails)}")
    for label in new_fails:
        print(f"  {label}: {sorted(set(after[label][1]) - set(before[label][1]))}")
    print("Every other answer that moves:")
    for label in corpus_labels(corpus):
        if label in read_right or before[label] == after[label]:
            continue
        print(f"  {label}: {before[label][0]} -> {after[label][0]}; "
              f"items fixed {sorted(set(before[label][1]) - set(after[label][1]))}")
    if sheet:
        truth = {u["label"]: u["truth"] for u in sheet}
        for name, scored in ((".3", sheet_old), (".4", sheet_new)):
            agree = sum(scored[label] == truth[label] for label in truth)
            print(f"Reading sheet, {name}: {agree} of {len(truth)} "
                  f"verdicts agree with the resolution")
    else:
        print("Reading sheet not present (evals/results is git-ignored)")
    return 0


def corpus_labels(corpus: list[dict]) -> list[str]:
    return [u["label"] for u in corpus]


if __name__ == "__main__":
    sys.exit(main())
