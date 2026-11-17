"""The harness with a frontier model in its answer seat. Paid.

    MODEL_ENGINEERING=<id> OPENROUTER_PROVIDER_ORDER=<order> \
    MEASURE_SET=<set> MEASURE_WORKFLOWS=answer-and-recompute \
    FRONTIER_EFFORT=medium python docs/probes/frontier_in_harness_probe.py \
        OUT_DIR SHARD SHARDS REPEATS MAX_SPEND [QUESTION_ID ...]

Run from the directory that holds the owner's `.env`. It needs the owner's
word and an amount before it is run.

It is docs/probes/short_workflows_measurement.py, unchanged, with one
addition made here and not in the harness: every request this process
sends for the model named in MODEL_ENGINEERING carries the reasoning
effort named in FRONTIER_EFFORT. The harness sends no reasoning effort of
its own, and the comparison is with that model asked directly at a stated
effort. Every other tier, the lookup, the checks and the delivery are the
harness as shipped. The environment names the answer model and its
provider for this process only; the owner's `.env` is not changed.
"""
from __future__ import annotations

import os
import runpy
from pathlib import Path

import httpx

MODEL = os.environ.get("MODEL_ENGINEERING", "").strip()
EFFORT = os.environ.get("FRONTIER_EFFORT", "medium").strip()
if not MODEL:
    raise SystemExit("MODEL_ENGINEERING names the answer model for this run")

_post = httpx.AsyncClient.post


async def _post_with_effort(self, url, *args, **kwargs):
    body = kwargs.get("json")
    if isinstance(body, dict) and body.get("model") == MODEL:
        kwargs["json"] = dict(body, reasoning={"effort": EFFORT})
    return await _post(self, url, *args, **kwargs)


httpx.AsyncClient.post = _post_with_effort

runpy.run_path(str(Path(__file__).with_name("short_workflows_measurement.py")),
               run_name="__main__")
