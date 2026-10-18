"""Repeat one tier-4 single-call unit N times, byte-identical to its calibration.

Option 1 of docs/reviews/2026-10-18-tier4-batch6-headroom-rate.md: is kimi-k3's
T4-42 miss stable, or a one-off from brief reasoning? The probe reuses the
runner's own treatment: the D-pages message (``runner.d_pages_message``), arm D's
system prompt and registered call (``runner._arm_single``), the batch's
max_tokens (R8), and the owner's ratified pin (``runner.tier4_pins``, R7). It
refuses to spend unless the message hashes to the calibration record's
``message_sha256``. Each call runs under the batch's per-unit ceiling.

Usage (repository root; paid):
    REPEAT_N=3 .venv/bin/python3 evals/tier4/probes/repeat_unit.py \
        evals/tier4/batch5 T4-42 docs/traces/20261018T180951Z-tier4-calibration-batch5.jsonl
"""
from __future__ import annotations

import asyncio, datetime, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals/tier4"))
import runner  # noqa: E402
from autornd.routing.openrouter import OpenRouterClient  # noqa: E402

N = int(os.environ.get("REPEAT_N", "3"))


async def main(batch_dir: str, qid: str, calibration: str) -> None:
    batch = runner.load_batch(ROOT / batch_dir)
    refusals = runner.check_freeze(batch)
    if refusals:
        raise SystemExit("freeze guard: " + "; ".join(refusals))
    cand = {c["id"]: c for c in json.load(open(batch.candidates_path))}[qid]
    unit = next(r for r in map(json.loads, open(ROOT / calibration))
                if r.get("question_id") == qid and r.get("arm") == "D-pages" and r.get("status"))
    message = runner.d_pages_message(cand, batch)
    digest = runner.message_sha256("D-pages", cand, batch)
    if digest != unit["message_sha256"]:
        raise SystemExit(f"message sha256 {digest} is not the calibration's {unit['message_sha256']}: refusing to spend")
    ceiling = batch.per_unit_ceilings["D-pages"]
    out = []
    with runner.tier4_pins(runner._ratified_provider_order()):
        for i in range(N):
            client = OpenRouterClient()
            client.spend_ceiling = ceiling
            t0 = time.time()
            try:
                answer, finish = await runner._arm_single(
                    "D", message, unit["serving"], client,
                    function_prefix="tier4", max_tokens=batch.single_call_max_tokens)
                rec = {"answer": answer, "finish_reasons": finish}
            except Exception as exc:
                rec = {"error": f"{type(exc).__name__}: {exc}"[:200]}
            rec.update({"repetition": i + 1, "seconds": round(time.time() - t0, 1), "cost": client.spend,
                        "providers": {k: sorted(v) for k, v in client.providers_by_function.items()}})
            out.append(rec)
            print(qid, i + 1, rec.get("finish_reasons") or rec.get("error", "")[:80],
                  f"${rec['cost']:.4f}", f"{rec['seconds']}s", flush=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    path = ROOT / f"evals/results/{stamp}-repeat-{qid}.json"
    json.dump({"batch": batch.name, "question_id": qid, "arm": "D-pages", "serving": unit["serving"],
               "message_sha256": digest, "calibration": calibration, "n": N, "ceiling_per_call": ceiling,
               "max_tokens": batch.single_call_max_tokens, "units": out,
               "spend": sum(r["cost"] for r in out)}, open(path, "w"), indent=1)
    print(f"spend ${sum(r['cost'] for r in out):.4f}; results {path}")


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:4]))
