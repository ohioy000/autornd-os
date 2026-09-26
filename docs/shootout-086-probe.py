"""Escalation shootout: Kimi-K3 vs Gemini-3.8-Flash, 3 autopsy questions each.

Pre-registered in docs/preregistration-086-escalation-shootout.md.
Same system prompt both sides, same max_tokens (65536), temperature 0.3,
provider pinned per call with fallbacks OFF (this is a measurement —
reproducibility over availability). Raw replies -> docs/traces/
086-escalation-shootout.jsonl for blind rating. Free text (no schema):
the escalation verdict shape would force autopsy prose into directive
fields; rating reads the prose.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, "/home/jb/autornd-os")
os.chdir("/home/jb/autornd-os")

from dotenv import load_dotenv

load_dotenv()

from autornd.engine.phases import ESCALATION_SYSTEM_PROMPT
from autornd.routing import openrouter as or_mod
from autornd.routing.openrouter import OpenRouterClient

Q1 = """2 implementation attempts failed validation on a message-queue capacity plan
(4,200 msg/s peak, 3x burst). Attempt 1: validate GREEN 7/7, judges fold agreed
4-0, full green build. Attempt 2 (rework): two reviewers truncated mid-JSON at
16384 completion tokens each (finish_reason=length), review recorded ship:false
with workflow_engine/high 'Specialist failed' findings, spend tripped $1.00 at
$1.27. Diagnose: model failure, ceiling failure, or loop failure? Name the fix
with least blast radius."""

Q2 = """Same model id (z-ai/glm-5.3) failed 9 times across 4 runs. Runs 1-2: 6 empty
replies at 16384 completion tokens (finish_reason=length, zero bytes) via Baidu
then Relace. Runs 3-5: 3 HTTP 404s at a 112768-token ask via Relace, Relace,
Alibaba — router 'Filter by Context Length' stripped all 39 endpoints despite
every listing showing max_out >= 131072. A sibling id (glm-5.3-prime, 1 endpoint)
served fine at the same ceiling via Alibaba. Which readings indict the model,
which indict the serving, which indict the router? What single experiment
separates the remaining confound?"""

Q3 = """Given this diagnosis: a full green build died in rework because two
reviewers truncated at an unwired 16k default while the configured ceiling was
112k, tripping a $1.00 spend cap at $1.27. Write the recovery directive: what
to change (ceiling, pin, serving, code), what to explicitly NOT change
(verdict semantics, gates, loop conditions), and the predicted terminal of the
next run. Must be executable by an implementer without re-diagnosing."""

QUESTIONS = [("Q1-ceiling", Q1), ("Q2-disambiguate", Q2), ("Q3-directive", Q3)]

SERVINGS = {
    "kimi-k3": ("moonshotai/kimi-k3", ["Moonshot AI"]),
    "gemini-3.8-flash": ("google/gemini-3.8-flash", ["Google"]),
}

PLAN = ("Plan: size a message queue at 4,200 msg/s peak with 3x burst; "
        "6 criteria covering sizing, cost, ops thresholds, consistency.")
TRIAGE = "Domains: backend. Risk: medium."
FAILURE_LOG = ("Failure log (2 attempts): "
               "[{iter 1: implement green, validate 7/7 PASS, fold 4-0 agree, "
               "rework triggered by review truncation}, "
               "{iter 2: review truncated 2x at 16384, ship:false}].")

OUT = "docs/traces/086-escalation-shootout.jsonl"


async def ask(client, model, order, qid, question):
    system = (ESCALATION_SYSTEM_PROMPT.format(n=2)
              + "\n\nArchitect's Plan:\n" + PLAN
              + "\n\nTriage Classification:\n- " + TRIAGE)
    user = ("The following 2 implementation attempts all failed validation. "
            "Analyze the failure pattern and produce a resolution directive.\n\n"
            "Failure Log:\n" + FAILURE_LOG
            + "\n\nScenario question (" + qid + "):\n" + question
            + "\n\nOriginal Request:\nProduce a capacity plan for a message "
              "queue sized at 4,200 messages per second peak with a 3x burst "
              "allowance. Reply as plain prose analysis followed by a "
              "directive — no JSON required.")
    orig_models = dict(client.FUNCTION_MODELS)
    orig_order = or_mod.provider_order_for
    client.FUNCTION_MODELS = {**orig_models, "escalation": model}
    or_mod.provider_order_for = lambda function: (
        list(order) if function == "escalation" else orig_order(function))
    orig_fb = or_mod.provider_fallbacks_allowed
    or_mod.provider_fallbacks_allowed = lambda: False
    t0 = time.time()
    try:
        data, resp = await client.chat_json(
            function="escalation", system_prompt=system, user_message=user,
            temperature=0.3, max_tokens=65536, schema=None,
        )
        secs = time.time() - t0
        return {"qid": qid, "model": model, "serving": resp.provider,
                "finish": resp.finish_reason, "secs": round(secs, 1),
                "prompt_tokens": resp.prompt_tokens,
                "completion_tokens": resp.completion_tokens,
                "cost": resp.cost, "reply": data if isinstance(data, dict)
                else {"text": data}}, resp.cost
    finally:
        client.FUNCTION_MODELS = orig_models
        or_mod.provider_order_for = orig_order
        or_mod.provider_fallbacks_allowed = orig_fb


async def main():
    client = OpenRouterClient()
    client.spend_ceiling = 1.00
    total = 0.0
    # Full 3x2 matrix, alternating servings per question (K,G / G,K / K,G —
    # no time-of-night bias). Missing-only mode: skips calls already in OUT.
    have = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            line = line.strip()
            if line:
                try:
                    d = json.loads(line)
                    have.add((d["qid"], d["model"]))
                except Exception:
                    pass
    calls = []
    for i, (qid, _) in enumerate(QUESTIONS):
        pair = ["kimi-k3", "gemini-3.8-flash"] if i % 2 == 0 else [
            "gemini-3.8-flash", "kimi-k3"]
        for side in pair:
            calls.append((qid, side))
    qmap = dict(QUESTIONS)
    with open(OUT, "a") as f:
        for qid, side in calls:
            model, pin = SERVINGS[side]
            if (qid, model) in have:
                print(f"skip {qid} -> {side} (already recorded)",
                      flush=True)
                continue
            print(f"asking {qid} -> {side} ...", flush=True)
            try:
                rec, cost = await ask(client, model, pin, qid, qmap[qid])
            except Exception as ex:
                rec = {"qid": qid, "model": model, "serving": side,
                       "error": f"{type(ex).__name__}: {ex}"}
                cost = 0.0
            total += cost or 0.0
            rec["spend_so_far"] = round(total, 4)
            f.write(json.dumps(rec) + "\n")
            f.flush()
            print(f"  done: {rec.get('completion_tokens')} tok, "
                  f"${(cost or 0):.4f} (total ${total:.4f})", flush=True)
    print(f"TRACE: {OUT}  SPEND: ${total:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
