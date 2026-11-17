"""A frontier model asked directly, with web search, on professional questions. Paid.

    FRONTIER_MODEL=<id> python docs/probes/frontier_direct_probe.py \
        OUT_FILE MAX_SPEND [LIMIT]

Run from the directory that holds the owner's `.env`. It needs the owner's
word and an amount before it is run.

No harness is in the path. Each question is one plain request to the model
named in FRONTIER_MODEL: the question as the only message, no system
prompt, the provider's web search switched on, reasoning effort medium.
That is what a person gets by asking the model directly. The answer, its
cited addresses, the token counts, the cost the provider reports and the
time are written one line a question.

The questions are drawn from the three professional sets by a fixed seed,
7, 9 and 6 of them, 22 in all: the draw is in the preregistration and is
checked here. It stops starting calls once the spend has reached MAX_SPEND.
LIMIT asks only the first LIMIT questions not yet in OUT_FILE, for a smoke.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = Path(sys.argv[1]).resolve()
MAX_SPEND = float(sys.argv[2])
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else None
MODEL = os.environ.get("FRONTIER_MODEL", "").strip()
sys.path.insert(0, str(ROOT))

from autornd.config import settings  # noqa: E402

SEED = "frontier-direct-20261117"
DRAW = (("questions.json", 7), ("hard-questions.json", 9),
        ("misleading-questions.json", 6))
# The most one call may write, reasoning included. A bound on a call's
# cost, not a target.
MAX_TOKENS = 8000
SEARCH_RESULTS = 5


def _questions() -> list[dict]:
    out = []
    for name, count in DRAW:
        frozen = json.loads((ROOT / "evals/professional" / name).read_text())
        ids = [q["id"] for q in frozen["questions"]]
        drawn = set(random.Random(f"{SEED}|{name}").sample(ids, count))
        out += [{"set": name, "id": q["id"], "question": q["question"]}
                for q in frozen["questions"] if q["id"] in drawn]
    return out


def _addresses(message: dict) -> list[str]:
    return [a["url_citation"]["url"] for a in message.get("annotations") or []
            if isinstance(a, dict) and isinstance(a.get("url_citation"), dict)
            and a["url_citation"].get("url")]


async def _ask(http: httpx.AsyncClient, question: dict) -> dict:
    started = time.time()
    record = {"set": question["set"], "id": question["id"], "model": MODEL}
    try:
        response = await http.post("/chat/completions", json={
            "model": MODEL,
            "messages": [{"role": "user", "content": question["question"]}],
            "max_tokens": MAX_TOKENS,
            "reasoning": {"effort": "medium"},
            "plugins": [{"id": "web", "max_results": SEARCH_RESULTS}],
            "usage": {"include": True},
        })
        body = response.json()
        if response.status_code != 200 or "choices" not in body:
            record.update({"status": "failed",
                           "error": json.dumps(body)[:400]})
        else:
            choice = body["choices"][0]
            message = choice.get("message") or {}
            usage = body.get("usage") or {}
            record.update({
                "status": "answered", "answer": message.get("content") or "",
                "finish_reason": choice.get("finish_reason"),
                "served_by": body.get("provider"),
                "citations": _addresses(message),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "reasoning_tokens": (usage.get("completion_tokens_details")
                                     or {}).get("reasoning_tokens"),
                "cost": usage.get("cost")})
    except Exception as exc:
        record.update({"status": "raised",
                       "error": f"{type(exc).__name__}: {exc}"[:400]})
    record["seconds"] = round(time.time() - started, 1)
    return record


async def main() -> None:
    if not MODEL:
        raise SystemExit("FRONTIER_MODEL names the model to ask")
    done, spent = set(), 0.0
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            row = json.loads(line)
            if row.get("status") == "answered":
                done.add(row["id"])
            spent += float(row.get("cost") or 0.0)
    todo = [q for q in _questions() if q["id"] not in done]
    if LIMIT is not None:
        todo = todo[:LIMIT]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    async with httpx.AsyncClient(
            base_url=settings.openrouter_base_url.rstrip("/"),
            headers=headers, timeout=600.0) as http:
        with OUT.open("a", encoding="utf-8") as log:
            for question in todo:
                if spent >= MAX_SPEND:
                    print("stopped at the spending limit", round(spent, 4))
                    break
                record = await _ask(http, question)
                spent += float(record.get("cost") or 0.0)
                record["spent"] = round(spent, 6)
                log.write(json.dumps(record) + "\n")
                log.flush()
                print(question["id"], record["status"], record.get("cost"),
                      record["seconds"], flush=True)
    print("spent", round(spent, 4))


asyncio.run(main())
