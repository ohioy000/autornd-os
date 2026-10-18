"""Option C, measured: does a blind recomputation catch what judging missed?

The advisor's probe of 2026-10-18 (the owner's "B then C, full permission").
A checker model receives only the request (and, for F2, the corpus pages)
and the names of the Results rows, never the answer, and computes those rows
itself. The comparison is mechanical: the answer is flagged when its
selection differs from the checker's, or a key numeric row differs by more
than TOL. It is measured on answers whose correctness the advisor's reading
established: three wrong T4-15 answers (the minor-axis torsional-flexural
coupling) and three correct controls.

Run from the repository root:
    .venv/bin/python3 evals/tier4/probes/recompute_check.py
Paid: a few calls on the standing research and judge tiers, under a client
spend ceiling of $1.00. Results go to evals/results/ (git-ignored) and the
advisor records the reading."""
from __future__ import annotations

import asyncio
import datetime
import json
import re


def ident(text):
    """An identifier, normalised: case, spacing and punctuation dropped,
    the words 'in parallel' dropped, and a count's multiplication sign
    (5 x EPC, 5 × EPC) read as a separator."""
    t = str(text).upper().replace("IN PARALLEL", "").replace("×", " ")
    t = re.sub(r"^\s*(\d+)\s*X\s+", r"\1 ", t)
    return re.sub(r"[^A-Z0-9]", "", t)

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from autornd.routing.openrouter import OpenRouterClient  # noqa: E402
from autornd.config import settings  # noqa: E402

TOL = 0.03
# (function, model, max_tokens): the judge tier's endpoint caps output at
# 16384 (measured 2026-10-18: 32768 was refused by the context-length filter).
CHECKERS = [("research", "google/gemini-3.8-flash", 32768), ("judge", "qwen/qwen3-235b-a22b-2507:exacto", 16384)]
import os
REPEAT = int(os.environ.get("RECOMPUTE_REPEAT", "1"))
ONLY = [q for q in os.environ.get("RECOMPUTE_ONLY", "").split(",") if q]
B2 = ROOT / "evals/tier4/batch2"
PILOT = ROOT / "evals/tier4/pilot"


def load(path):
    return {c["id"]: c for c in json.load(open(path))}


def pages(batch_dir, qid):
    m = json.load(open(batch_dir / "manifest.json"))
    return "\n\n".join(Path(ROOT / p).read_text() for p in m["corpus"].get(qid, {}).get("pages", []))


def rows_of(request):
    tail = request.split("with these rows:", 1)[1]
    return [r.strip().rstrip(".") for r in re.split(r",\s*(?![^()]*\))", tail) if r.strip()]


def _clean(text):
    for junk in ("\\(", "\\)", "$", "**", "\\mathrm", "\\text", "\\bar", "\\"):
        text = text.replace(junk, "")
    return text.replace("{", "").replace("}", "").strip()


def parse_table(answer):
    """The answer's Results table as {row: value string}, read whether the
    table is laid out one row per quantity or as one header row and one
    data row."""
    block = answer.rsplit("Results", 1)[-1] if "Results" in answer else answer
    rows = []
    for line in block.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [_clean(c) for c in line.strip().strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    if len(rows) >= 2 and len(rows[0]) > 2 and len(rows[1]) == len(rows[0]):
        return dict(zip(rows[0], rows[1]))          # one header row, one data row
    return {r[0]: r[1] for r in rows if len(r) >= 2 and r[0]}


def num(text):
    m = re.search(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?", str(text).replace(",", ""))
    return float(m.group()) if m else None


def norm(key):
    return re.sub(r"[^a-z0-9]", "", _clean(key).lower().split("(")[0].replace("lambda", "lambda"))


def signature(key):
    """A row name's letters and digits, sorted: matches 'lambda_bar' to
    'bar lambda' and 'N_{cr,TF}' to 'N_cr_TF'."""
    return "".join(sorted(norm(key)))


def find(rows, key):
    by_norm = {norm(k): v for k, v in rows.items()}
    if norm(key) in by_norm:
        return by_norm[norm(key)]
    by_sig = {signature(k): v for k, v in rows.items()}
    return by_sig.get(signature(key))


def same_choice(a, c):
    return ident(_clean(str(a))) == ident(_clean(str(c)))


def compare(answer_rows, checker_rows, key_rows):
    """Differences on the key rows: the first key row is the selection,
    compared as an identifier; the rest numerically within TOL."""
    diffs = []
    for i, k in enumerate(key_rows):
        av, cv = find(answer_rows, k), find(checker_rows, k)
        if av is None or cv is None:
            continue
        if i == 0:
            if not same_choice(av, cv):
                diffs.append((k, av, cv))
            continue
        an, cn = num(av), num(cv)
        if an is not None and cn is not None and abs(an - cn) > TOL * max(abs(cn), 1e-9):
            diffs.append((k, an, cn))
    return diffs


def traces():
    for f in ["20261017T210922Z-tier4-calibration-batch2.jsonl", "20261017T234014Z-tier4-calibration-batch2.jsonl",
              "20261018T022735Z-tier4-pilot-batch2.jsonl", "20261017T021010Z-tier4-calibration.jsonl"]:
        for line in open(ROOT / "docs/traces" / f):
            r = json.loads(line)
            if r.get("record") == "unit" and r.get("answer"):
                yield f, r


async def main():
    b2, p1 = load(B2 / "candidates.json"), load(PILOT / "candidates.json")
    questions = {"T4-15": (b2["T4-15"], pages(B2, "T4-15")), "T4-16": (b2["T4-16"], pages(B2, "T4-16")),
                 "T4-04": (p1["T4-04"], "")}
    key = {"T4-15": ["Section", "N_cr_TF (kN)", "lambda_bar", "N_b_Rd (kN)"],
           "T4-16": ["Model", "D_trim (mm)", "H_sys (m)", "NPSH_A (m)", "P_shaft (kW)"],
           "T4-04": ["Fan_ID", "N_f (-)", "R_th (K/W)", "T_b (degC)"]}
    # the answers whose correctness the advisor's reading established
    answers = []
    for f, r in traces():
        q = r["question_id"]
        if q == "T4-15":
            answers.append((f"{f[:16]} {r['arm']}", q, r["answer"], "wrong"))
        if q == "T4-16" and r.get("finish_reasons") == ["stop"]:
            answers.append((f"{f[:16]} {r['arm']}", q, r["answer"], "correct"))
        if q == "T4-04" and r.get("finish_reasons") == ["stop"]:
            answers.append((f"{f[:16]} {r['arm']}", q, r["answer"], "correct"))
    ref = b2["T4-15"]["reference_design"]
    answers.append(("verified reference", "T4-15", "Results\n" + "\n".join(f"| {k} | {v} |" for k, v in ref.items()), "correct"))
    client = OpenRouterClient(api_key=settings.openrouter_api_key)
    client.spend_ceiling = 1.00
    checker_out = {}
    for function, model, max_tokens in CHECKERS:
        for q, (cand, corpus) in questions.items():
          if ONLY and q not in ONLY:
              continue
          for rep in range(REPEAT):
            rows = rows_of(cand["request"])
            q_key = (model, q) if REPEAT == 1 else (model, f"{q}#{rep + 1}")
            prompt = (cand["request"] + (f"\n\nReference documents:\n\n{corpus}" if corpus else "")
                      + "\n\nCompute the design yourself. Reply with ONE JSON object only, keys exactly these "
                      "Results rows, values your computed results: " + json.dumps(rows))
            try:
                resp = await client.chat(function=function, model=model, system_prompt="You are a careful senior engineer.",
                                         user_message=prompt, max_tokens=max_tokens)
                text = resp.content or ""
                obj = json.loads(text[text.find("{"):text.rfind("}") + 1]) if "{" in text else {}
            except Exception as exc:
                obj = {"_error": f"{type(exc).__name__}: {exc}"[:200]}
            checker_out[q_key] = obj
            print(f"checker {model} on {q_key[1]}: {json.dumps(obj)[:300]}", flush=True)
    results = []
    for label, q, answer, truth in answers:
        arows = parse_table(answer)
        for function, model, _ in CHECKERS:
          for (m, qk), crow in checker_out.items():
            if m != model or qk.split("#")[0] != q:
                continue
            diffs = compare(arows, {k: v for k, v in crow.items() if not k.startswith("_")}, key[q]) if crow and "_error" not in crow else None
            flagged = None if diffs is None else bool(diffs)
            results.append({"answer": label, "question": q, "sample": qk, "truth": truth, "checker": model, "flagged": flagged, "diffs": diffs})
            print(f"{qk:8s} {label:32s} truth={truth:7s} checker={model.split('/')[1][:18]:18s} flagged={flagged} {diffs}", flush=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / f"evals/results/{stamp}-recompute-check.json"
    json.dump({"checkers": CHECKERS, "tol": TOL, "checker_outputs": {f"{m}|{q}": v for (m, q), v in checker_out.items()},
               "results": results, "spend": client.spend, "providers": {k: sorted(v) for k, v in client.providers_by_function.items()}},
              open(out, "w"), indent=1, default=str)
    print(f"spend ${client.spend:.4f}; results {out}")

if __name__ == "__main__":
    asyncio.run(main())
