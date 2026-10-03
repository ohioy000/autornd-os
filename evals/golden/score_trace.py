"""Score a results JSONL against the golden keys (ARCH-20261001-102).

Usage: python3 evals/golden/score_trace.py <results.jsonl>

Executor-written. It reads the advisor's keys.json and calls the advisor's
score.py, unchanged; it decides nothing score.py does not. The answer text:
- a completed run: verdicts.implement.summary (SHIPPED);
- a blocked run whose watchdog points at an agreed iteration:
  iterations[index].implement_summary, scored as 'approved, not shipped'
  (diagnostic only; it can never pass);
- a baseline's `record: "answer"` row: its answer, scored as 'direct answer'
  (ARCH-20261002-115 — one tool re-scores every recorded run);
- otherwise there is no answer.
A question passes under keys.json's pass_rule: shipped, every item holds
(and, for Q5, the order holds), and seconds <= time_target_s.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score as golden  # noqa: E402  (the advisor's scorer, unchanged)

KEYS = json.loads(Path(golden.KEYS).read_text(encoding="utf-8"))
BY_ID = {q["id"]: q for q in KEYS["golden"]}
BY_ID["IA"] = KEYS["side_test"]
# Ruling D44: every report states the key version beside each score.
KEY_LABEL = f"key v{KEYS['version']}"


def key_for(scenario_id: str) -> dict | None:
    """golden_q3 -> Q3; golden_side_ia -> IA."""
    m = re.fullmatch(r"golden_(?:side_)?(\w+)", scenario_id)
    return BY_ID.get(m.group(1).upper()) if m else None


def answer_of(unit: dict) -> tuple[str | None, str]:
    if unit.get("status") == "completed":
        impl = (unit.get("verdicts") or {}).get("implement") or {}
        return impl.get("summary"), "shipped"
    approved = ((unit.get("watchdog") or {}).get("approved") or {})
    index = approved.get("index")
    iterations = unit.get("iterations") or []
    if index is not None and 0 <= index < len(iterations):
        return iterations[index].get("implement_summary"), "approved, not shipped"
    return None, "no answer"


def score_unit(unit: dict, header: dict) -> dict:
    q = key_for(unit["scenario"])
    answer, kind = answer_of(unit)
    row = {"scenario": unit["scenario"], "key": q["id"] if q else None,
           "status": unit.get("status"), "answer": kind,
           "seconds": unit.get("seconds"), "target_s": q and q["time_target_s"],
           "cost": round(unit.get("cost") or 0.0, 4), "cap": header.get("max_spend"),
           "risk": ((unit.get("verdicts") or {}).get("triage") or {}).get("risk"),
           "reason": unit.get("reason")}
    if q is None:
        return {**row, "verdict": "UNKEYED"}
    if answer is None:
        return {**row, "items": {}, "verdict": "FAIL (no answer)"}
    if q["id"] == "IA":
        t = golden.normalize(answer)
        items = {it["id"]: golden.item_holds(it, t) for it in q["core_items"]}
        supplementary = {it["id"]: golden.item_holds(it, t)
                         for it in q["supplementary_items"]}
    else:
        items = golden.score(q, answer)
        supplementary = {}
    norm = golden.normalize(answer)
    sprawl = len(answer) / max(1, len(q["model_answer"]))
    scope_hits = sum(1 for term in q.get("scope_out", []) if term.lower() in norm)
    within = row["seconds"] is not None and row["seconds"] <= q["time_target_s"]
    passed = kind == "shipped" and all(items.values()) and within
    return {**row, "items": items, "supplementary": supplementary,
            "within_target": within, "sprawl": round(sprawl, 1),
            "scope_out_hits": scope_hits, "answer_chars": len(answer),
            "verdict": "PASS" if passed else "FAIL"}


def score_answer_row(row: dict, header: dict) -> dict:
    """A baseline's `record: "answer"` row: the answer IS the deliverable.

    ARCH-20261002-115: this tool read unit rows only, so 107's direct-call
    baseline scored 0/0 — six answers sitting in the file, invisible. The
    regression vectors in score.py have read both shapes from the start
    ('scenario' or 'id'); only this reader was narrow (convention 28: no
    evidence reported as no problem).
    """
    q = BY_ID.get(row.get("id"))
    answer = row.get("answer")
    kind = "direct answer" if answer else "no answer"
    base = {"scenario": row.get("id"), "key": q["id"] if q else None,
            "status": "direct" if answer else
                      ("error" if row.get("error") else "skipped"),
            "answer": kind,
            "seconds": row.get("seconds"), "target_s": q and q["time_target_s"],
            "cost": round(row.get("cost") or 0.0, 4),
            "cap": header.get("max_spend_total") or header.get("max_spend"),
            "risk": "direct",
            "reason": row.get("error") or row.get("reason")}
    if q is None:
        return {**base, "verdict": "UNKEYED"}
    if not answer:
        return {**base, "items": {}, "verdict": "FAIL (no answer)"}
    if q["id"] == "IA":
        t = golden.normalize(answer)
        items = {it["id"]: golden.item_holds(it, t) for it in q["core_items"]}
        supplementary = {it["id"]: golden.item_holds(it, t)
                         for it in q["supplementary_items"]}
    else:
        items = golden.score(q, answer)
        supplementary = {}
    norm = golden.normalize(answer)
    sprawl = len(answer) / max(1, len(q["model_answer"]))
    scope_hits = sum(1 for term in q.get("scope_out", []) if term.lower() in norm)
    within = row["seconds"] is not None and row["seconds"] <= q["time_target_s"]
    passed = bool(answer) and all(items.values()) and within
    return {**base, "items": items, "supplementary": supplementary,
            "within_target": within, "sprawl": round(sprawl, 1),
            "scope_out_hits": scope_hits, "answer_chars": len(answer),
            "verdict": "PASS" if passed else "FAIL"}


def main(path: str) -> list[dict]:
    lines = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    header = next((l for l in lines if l.get("record") == "header"), {})
    rows = [score_unit(u, header) if u.get("record") == "unit"
            else score_answer_row(u, header)
            for u in lines if u.get("record") in ("unit", "answer")]
    for r in rows:
        held = "".join("+" if v else "-" for v in r.get("items", {}).values())
        print(f"{r['key'] or r['scenario']:<4} {r['verdict']:<18} {r['status']:<10} "
              f"{r['answer']:<22} items[{held}] {r['seconds']}s/{r['target_s']}s "
              f"${r['cost']}/{r['cap']} risk={r['risk']} "
              f"sprawl={r.get('sprawl')} scope_out={r.get('scope_out_hits')}")
        failed = [i for i, v in r.get("items", {}).items() if not v]
        if failed:
            print(f"     items not held: {failed}")
        if r.get("supplementary"):
            print(f"     supplementary: {r['supplementary']}")
    passes = sum(r["verdict"] == "PASS" for r in rows)
    shipped = sum(r["answer"] in ("shipped", "direct answer") for r in rows)
    sprawls = [r["sprawl"] for r in rows if r.get("sprawl") is not None]
    print(f"\n{passes}/{len(rows)} PASS · {shipped}/{len(rows)} shipped · "
          f"median sprawl {statistics.median(sprawls) if sprawls else None} · "
          f"total ${round(sum(r['cost'] for r in rows), 4)} · {KEY_LABEL}")
    return rows


if __name__ == "__main__":
    main(sys.argv[1])
