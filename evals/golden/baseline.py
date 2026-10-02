"""The direct-call baseline (ARCH-20261002-107).

Usage: python -m evals.golden.baseline <out.jsonl> [--max-spend-call 0.02] [--max-spend-total 0.10]

Executor-written measurement (allowed under D41). Each golden question and
the IA side test goes to the engineering tier in ONE call, through the
harness's own OpenRouterClient (so it is priced, pinned and guarded like any
other call). The user message is the request from keys.json, byte for byte;
the system message is the advisor's sentence below, exactly. No plan,
grounding, criteria, review, or retry on content. Each answer is scored with
the advisor's score.py, unchanged.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score as golden  # noqa: E402  (the advisor's scorer, unchanged)

SYSTEM = "You are an expert engineer. Answer the question directly, correctly and concisely."
MAX_TOKENS = 4000
KEYS = json.loads(Path(golden.KEYS).read_text(encoding="utf-8"))
# Ruling D44: every report states the key version beside each score.
KEY_LABEL = f"key v{KEYS['version']}"


def questions() -> list[dict]:
    return list(KEYS["golden"]) + [KEYS["side_test"]]


def score_answer(q: dict, answer: str) -> dict[str, bool]:
    if q["id"] == "IA":
        t = golden.normalize(answer)
        return {it["id"]: golden.item_holds(it, t) for it in q["core_items"]}
    return golden.score(q, answer)


async def run(client_factory, out: Path, per_call: float, total: float) -> list[dict]:
    from autornd.routing.openrouter import BudgetExceeded, provider_order_for

    probe = client_factory()
    header = {"record": "header", "command": "ARCH-20261002-107",
              "key_version": KEY_LABEL,
              "model": probe.get_model("engineering"),
              "pin": provider_order_for("engineering"), "system": SYSTEM,
              "max_tokens": MAX_TOKENS, "max_spend_call": per_call,
              "max_spend_total": total}
    rows, spent = [], 0.0
    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(header) + "\n"); fh.flush()
        for q in questions():
            row: dict = {"record": "answer", "id": q["id"]}
            if spent + per_call > total + 1e-9:
                row.update(skipped=True, reason="total cap would not fit one more call")
            else:
                client = client_factory()
                client.spend_ceiling = per_call
                started = time.perf_counter()
                try:
                    resp = await client.chat("engineering", SYSTEM, q["request"],
                                             max_tokens=MAX_TOKENS)
                    row.update(answer=resp.content, finish_reason=resp.finish_reason,
                               provider=resp.provider, prompt_tokens=resp.prompt_tokens,
                               completion_tokens=resp.completion_tokens, cost=resp.cost)
                except BudgetExceeded as exc:
                    row.update(answer=None, error=str(exc), cost=client.spend)
                finally:
                    row["seconds"] = round(time.perf_counter() - started, 3)
                    spent += client.spend
                    await client.close()
                if row.get("answer"):
                    items = score_answer(q, row["answer"])
                    row.update(items=items, all_hold=all(items.values()),
                               sprawl=round(len(row["answer"]) / len(q["model_answer"]), 1))
            rows.append(row)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n"); fh.flush()
    return rows


def report(rows: list[dict]) -> str:
    lines = []
    for r in rows:
        held = "".join("+" if v else "-" for v in (r.get("items") or {}).values())
        lines.append(f"{r['id']:<3} {'ALL HOLD' if r.get('all_hold') else 'FAIL':<9} "
                     f"items[{held}] {r.get('seconds')}s ${r.get('cost', 0):.4f} "
                     f"sprawl={r.get('sprawl')} finish={r.get('finish_reason')}")
    golden_rows = [r for r in rows if r["id"] != "IA"]
    sprawls = [r["sprawl"] for r in golden_rows if r.get("sprawl") is not None]
    lines.append(f"{sum(bool(r.get('all_hold')) for r in golden_rows)}/6 golden hold every item · "
                 f"median sprawl {statistics.median(sprawls) if sprawls else None} · "
                 f"total ${sum(r.get('cost', 0) or 0 for r in rows):.4f} · {KEY_LABEL}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    from autornd.routing.openrouter import OpenRouterClient, check_models

    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--max-spend-call", type=float, default=0.02)
    ap.add_argument("--max-spend-total", type=float, default=0.10)
    a = ap.parse_args()

    async def main():
        await check_models()          # rates, so the 104 guard is not blind
        rows = await run(OpenRouterClient, Path(a.out), a.max_spend_call, a.max_spend_total)
        print(report(rows))
    asyncio.run(main())
