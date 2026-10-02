"""ARCH-20261002-107: the direct-call baseline sends each request byte for
byte, with the advisor's system message, in one call, and scores the answer
with the advisor's keys. Provider-free: the real OpenRouterClient.chat over
an httpx MockTransport whose 'model' answers with each key's model answer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

from autornd.routing.openrouter import OpenRouterClient

GOLDEN = Path(__file__).resolve().parent.parent / "evals" / "golden"
sys.path.insert(0, str(GOLDEN))
import baseline  # noqa: E402

KEYS = json.loads((GOLDEN / "keys.json").read_text(encoding="utf-8"))
BY_REQUEST = {q["request"]: q["model_answer"]
              for q in KEYS["golden"] + [KEYS["side_test"]]}


def _factory(sent: list):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body)
        user = body["messages"][1]["content"]
        return httpx.Response(200, json={
            "choices": [{"message": {"content": BY_REQUEST.get(user, "no idea")},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 50, "cost": 0.001},
            "provider": "Test", "model": body["model"]})

    def make():
        c = OpenRouterClient(api_key="k", base_url="https://router.test/api/v1")
        c._client = httpx.AsyncClient(base_url=c.base_url,
                                      transport=httpx.MockTransport(handler))
        return c
    return make


class TestTheBaselineSendsVerbatimAndScores:
    async def test_one_call_each_verbatim_with_the_exact_system_message(self, tmp_path):
        sent: list = []
        rows = await baseline.run(_factory(sent), tmp_path / "b.jsonl", 0.02, 0.10)
        assert len(sent) == 7                                  # one call each
        for body, q in zip(sent, baseline.questions()):
            assert body["messages"][0]["content"] == baseline.SYSTEM
            assert body["messages"][1]["content"] == q["request"]   # byte-identical
            assert body["max_tokens"] == baseline.MAX_TOKENS
        assert baseline.SYSTEM == ("You are an expert engineer. Answer the question "
                                   "directly, correctly and concisely.")
        # The model answers hold every item of their keys.
        assert all(r["all_hold"] for r in rows), [r["id"] for r in rows if not r["all_hold"]]
        written = [json.loads(l) for l in (tmp_path / "b.jsonl").read_text().splitlines()]
        assert written[0]["record"] == "header" and len(written) == 8
        assert written[1]["items"] and written[1]["sprawl"] == 1.0

    async def test_a_wrong_answer_is_scored_as_failing(self, tmp_path):
        rows = await baseline.run(_factory([]), tmp_path / "b.jsonl", 0.02, 0.10)
        assert all(r["all_hold"] for r in rows)
        bad = baseline.score_answer(KEYS["golden"][0], "Output 6 V; current 3 mA.")
        assert not all(bad.values())

    async def test_the_trace_header_and_report_name_the_key_version(self, tmp_path):
        # Ruling D44: every report states the key version beside each score.
        rows = await baseline.run(_factory([]), tmp_path / "b.jsonl", 0.02, 0.10)
        written = [json.loads(l) for l in (tmp_path / "b.jsonl").read_text().splitlines()]
        label = f"key v{KEYS['version']}"
        assert written[0]["key_version"] == label
        assert baseline.report(rows).splitlines()[-1].endswith(label)
