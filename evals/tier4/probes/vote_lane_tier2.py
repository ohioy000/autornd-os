"""Step 2 of the owner's "1 then 2": the vote lane measured on the 25 frozen
tier-2 questions.

Four independent gemini-flash calls answer each question with the tier-3 arm-A
prompt, each ending with a FINAL JSON block of its final numbers and verdicts.
Sample 1 is the delivered answer, and samples 2-4 are the blind checkers. The
answer is flagged when one of its final numbers has no match within TOL in at
least two checkers, or when its verdict set differs from at least two
checkers'. Correctness is the advisor's hand reading of every delivered answer
against the keys, with the frozen tier-2 scorer only as the screen (D50).

Key-free by construction: the comparison never reads the keys, only the four
answers. Its known limit: a procedure's steps are not numbers or verdicts, so a
missing step is invisible to it.

Usage (repository root):
    .venv/bin/python3 evals/tier4/probes/vote_lane_tier2.py sample   # paid
    .venv/bin/python3 evals/tier4/probes/vote_lane_tier2.py score FILE
"""
from __future__ import annotations

import asyncio, datetime, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from autornd.routing.openrouter import OpenRouterClient  # noqa: E402
from autornd.config import settings  # noqa: E402

FUNCTION, MODEL, MAX_TOKENS, SAMPLES, TOL, CEILING = "research", "google/gemini-3.8-flash", 16384, 4, 0.03, 2.50
SUFFIX = ("\n\nAfter your answer, end with a JSON object in a fenced block, exactly in this shape: "
          '{"values": [every final numeric result you report, as plain numbers in the units you stated], '
          '"verdicts": [every final verdict or selection word you report, e.g. "PASS", "FAIL", "330 ohm"]}. '
          "Final results only, not intermediate values.")


def final_block(text):
    """The answer's FINAL JSON, and the answer with that block removed."""
    m = list(re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S))
    if not m:
        return {}, text
    try:
        obj = json.loads(m[-1].group(1))
    except ValueError:
        obj = {}
    return obj, text[:m[-1].start()].rstrip()


def norm_verdict(v):
    return re.sub(r"[^A-Z0-9.]", "", str(v).upper())


def flag(answer, checkers):
    """Returns (flagged, reasons). An answer value is unsupported when fewer
    than two checkers report a value within TOL of it."""
    reasons = []
    vals = [x for x in answer.get("values", []) if isinstance(x, (int, float))]
    for v in vals:
        support = sum(1 for c in checkers if any(isinstance(x, (int, float)) and abs(x - v) <= TOL * max(abs(v), 1e-9) for x in c.get("values", [])))
        if support < 2:
            reasons.append(f"value {v} supported by {support}/3")
    av = {norm_verdict(x) for x in answer.get("verdicts", [])}
    agree = sum(1 for c in checkers if {norm_verdict(x) for x in c.get("verdicts", [])} == av)
    if agree < 2:
        reasons.append(f"verdicts {sorted(av)} matched by {agree}/3")
    return bool(reasons), reasons


async def sample():
    qj = json.load(open(ROOT / "evals/tier2/questions.json"))
    questions = qj if isinstance(qj, list) else qj["questions"]
    template = (ROOT / "evals/tier3/prompts/arm_a.md").read_text()

    def render(question):
        """The tier-3 arm-A rendering: the text before ## QUESTION is the
        system prompt, the rest the user message."""
        head, _, tail = template.replace("{{QUESTION_TEXT}}", question).partition("## QUESTION")
        return head.strip(), ("## QUESTION" + tail).strip()
    client = OpenRouterClient(api_key=settings.openrouter_api_key)
    client.spend_ceiling = CEILING
    out = {}
    for q in questions:
        qid = q["id"]; text = q.get("question") or q.get("text")
        out[qid] = []
        for i in range(SAMPLES):
            try:
                system, user = render(text)
                resp = await client.chat(function=FUNCTION, model=MODEL, system_prompt=system, user_message=user + SUFFIX, max_tokens=MAX_TOKENS)
                out[qid].append({"answer": resp.content or "", "finish": getattr(resp, "finish_reason", None)})
            except Exception as exc:
                out[qid].append({"error": f"{type(exc).__name__}: {exc}"[:200]})
        print(qid, [("ok" if "answer" in s else s["error"][:40]) for s in out[qid]], f"spend ${client.spend:.3f}", flush=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    path = ROOT / f"evals/results/{stamp}-vote-lane-tier2.json"
    json.dump({"model": MODEL, "samples": SAMPLES, "tol": TOL, "max_tokens": MAX_TOKENS, "out": out, "spend": client.spend,
               "providers": {k: sorted(v) for k, v in client.providers_by_function.items()}}, open(path, "w"), indent=1)
    print(f"spend ${client.spend:.4f}; samples {path}")


def score(path):
    sys.path.insert(0, str(ROOT))
    from evals.tier2 import scorer
    d = json.load(open(path))["out"]
    rows = []
    for qid, samples in d.items():
        parsed = []
        for s in samples:
            obj, body = final_block(s.get("answer", ""))
            verdict = scorer.score(qid, body)["verdict"] if body else "NONE"
            parsed.append((obj, body, verdict))
        answer, checkers = parsed[0], [p[0] for p in parsed[1:]]
        flagged, reasons = flag(answer[0], checkers) if answer[0] else (None, ["no FINAL block"])
        rows.append((qid, answer[2], [p[2] for p in parsed[1:]], flagged, reasons))
        print(f"{qid}: answer scorer={answer[2]} checkers={[p[2] for p in parsed[1:]]} flagged={flagged} {reasons[:2]}")
    return rows


if __name__ == "__main__":
    if sys.argv[1] == "sample":
        asyncio.run(sample())
    elif sys.argv[1] == "score":
        score(sys.argv[2])
