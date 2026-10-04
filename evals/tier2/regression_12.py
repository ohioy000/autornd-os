"""The tier-2 scorer's regression vectors (Ruling D50 (1)).

The twelve recorded real answers to tier-2 Q1-Q5, read from the
committed measurement records and scored with this package's
scorer. Tier-2 Q1-Q5 are the golden Q1-Q5 word for word, so the
record already holds real answers to them:

- 107's direct answers to Q1-Q5 (docs/traces/107-direct-baseline.jsonl,
  its ``record: "answer"`` rows),
- 102's pipeline answers to Q1, Q2, Q4, Q5
  (docs/traces/102-golden-arm-b.jsonl, unit rows read through
  evals.golden.score_trace.answer_of),
- 106's pipeline answers to Q1, Q4, Q5
  (docs/traces/106-golden-arm-b.jsonl, same reader).

Every one of the twelve was read correct by two readers on
2026-10-02 (the advisor's pre-run review; the recorded readings).
The frozen scorer (frozen-2026-10-03) passed 5 of the 12; the
repaired version must pass all twelve, and this probe is the
regression vector set that proves it. Run it to print the vectors:

    .venv/bin/python3 evals/tier2/regression_12.py

The vectors are read from the traces, never hand-copied: the
answer text is the measurement record's own bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRACES = HERE.parent.parent / "docs" / "traces"

# (trace file, record shape) -> the twelve vectors.
DIRECT = ("107-direct-baseline.jsonl", "answer")
PIPELINES = (
    ("102-golden-arm-b.jsonl", ("Q1", "Q2", "Q4", "Q5")),
    ("106-golden-arm-b.jsonl", ("Q1", "Q4", "Q5")),
)


def load_vectors() -> list[tuple[str, str, str]]:
    """The twelve vectors: (run, question_id, answer text).

    Unit rows are read through evals.golden.score_trace.answer_of
    (the same reader the record was scored with): a completed
    run's terminal conclusion, or a blocked run's
    watchdog-approved iteration.
    """
    sys.path.insert(0, str(HERE.parent / "golden"))
    from score_trace import answer_of  # noqa: E402

    vectors: list[tuple[str, str, str]] = []

    # 107's direct answers: its answer rows carry the question id
    # and the answer text verbatim.
    lines = [json.loads(l) for l in
             (TRACES / DIRECT[0]).read_text(encoding="utf-8").splitlines()
             if l.strip()]
    for row in lines:
        if row.get("record") == "answer" and row.get("id") in (
                "Q1", "Q2", "Q3", "Q4", "Q5"):
            vectors.append(("107-direct", row["id"], row["answer"]))

    # Pipeline answers: unit rows through answer_of.
    for trace, ids in PIPELINES:
        lines = [json.loads(l) for l in
                 (TRACES / trace).read_text(encoding="utf-8").splitlines()
                 if l.strip()]
        for row in lines:
            if row.get("record") != "unit":
                continue
            scenario = row.get("scenario", "")
            if not scenario.startswith("golden_"):
                continue
            qid = scenario[len("golden_"):].upper()
            if qid not in ids:
                continue
            answer, _kind = answer_of(row)
            if answer:
                vectors.append((trace[:3], qid, answer))

    # The registered set: five from 107, four from 102, three from 106.
    assert len(vectors) == 12, f"expected 12 vectors, found {len(vectors)}"
    return vectors


def print_vectors(scorer) -> int:
    """Score every vector and print the item-by-item reading.

    Returns the number of vectors whose every required item passes.
    """
    passed = 0
    for run, qid, answer in load_vectors():
        result = scorer.score(qid, answer)
        items = result["items"]
        held = [i["pass"] for i in items]
        if all(held):
            passed += 1
        print(f"{run} {qid}: {result['passed_items']}/"
              f"{result['total_items']} items "
              f"({result['verdict']})")
        for i in items:
            if not i["pass"]:
                print(f"    FAIL [{i['item']}] {i['detail']}")
    print(f"\n{passed}/12 questions pass under "
          f"{getattr(scorer, 'SCORER_VERSION', '?')}")
    return passed


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(HERE))
    import scorer  # noqa: E402  (this package's scorer)

    print_vectors(scorer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
