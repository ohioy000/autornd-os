"""Option C, step 2: majority-of-N blind recomputation as a check.

N samples of one cheap checker model recompute a question's Results rows
from the request and its corpus pages alone, never seeing an answer. For each
key row the majority value is the one at least ceil(N/2)+... i.e. at least 2
of 3 samples agree on within TOL (identifiers: exact). An answer is flagged
when it disagrees with a majority value; a row with no majority flags nothing
and is reported as no consensus.

Usage (repository root):
    .venv/bin/python3 evals/tier4/probes/recompute_vote.py sample     # paid: N samples per question
    .venv/bin/python3 evals/tier4/probes/recompute_vote.py score FILE  # free: score answers in traces
"""
from __future__ import annotations

import asyncio, datetime, json, os, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
import recompute_check as rc  # noqa: E402

N = int(os.environ.get("VOTE_N", "3"))
FUNCTION, MODEL, MAX_TOKENS = "research", "google/gemini-3.8-flash", 32768
BATCHES = {"batch2": ROOT / "evals/tier4/batch2", "batch3": ROOT / "evals/tier4/batch3", "batch4": ROOT / "evals/tier4/batch4"}
KEY_ROWS = {
    "T4-15": ["Section", "N_cr_TF (kN)", "lambda_bar", "N_b_Rd (kN)"],
    "T4-21": ["Model", "RMS Output Torque (N·m)", "Derated Thermal Torque Limit (N·m)", "Peak Motor Torque (N·m)"],
    "T4-22": ["Model", "Required Cv at Max Flow", "Allowable Incipient Pressure Drop dP_ic (kPa)"],
    "T4-23": ["Model", "Corrected Pressure Drop (kPa)", "Coolant Outlet Temp (°C)", "Peak Baseplate Temp (°C)"],
    "T4-24": ["Bank Configuration", "Derated Working Voltage Limit (V)", "Effective Ripple Current per Capacitor (A_rms)", "Core Hot-Spot Temp (°C)"],
    "T4-32": ["selected_model", "I_allow_A", "Ith_allow_A"],
    "T4-33": ["selected_model", "Q_del_m3_s", "H_del_m", "P_shaft_kW", "NPSHr_visc_m"],
    "T4-34": ["selected_model", "R_req_K_per_W", "R_sa_K_per_W"],
}
QUESTIONS = {"T4-15": "batch2", "T4-21": "batch3", "T4-22": "batch3", "T4-23": "batch3", "T4-24": "batch3",
             "T4-32": "batch4", "T4-33": "batch4", "T4-34": "batch4"}
ONLY = [q for q in os.environ.get("VOTE_ONLY", "").split(",") if q]


def majority(values, is_id):
    """The value at least 2 samples agree on (within TOL for numbers), or None."""
    vals = [v for v in values if v is not None]
    if is_id:
        counts = Counter(rc.ident(v) for v in vals)
        top = counts.most_common(1)
        return top[0][0] if top and top[0][1] >= 2 else None
    nums = [rc.num(v) for v in vals if rc.num(v) is not None]
    for a in nums:
        agree = [b for b in nums if abs(a - b) <= rc.TOL * max(abs(a), 1e-9)]
        if len(agree) >= 2:
            return sum(agree) / len(agree)
    return None


async def sample():
    client = rc.OpenRouterClient(api_key=rc.settings.openrouter_api_key)
    client.spend_ceiling = 2.00
    out = {}
    for q, bname in QUESTIONS.items():
        if ONLY and q not in ONLY:
            continue
        cand = rc.load(BATCHES[bname] / "candidates.json")[q]
        corpus = rc.pages(BATCHES[bname], q)
        rows = rc.rows_of(cand["request"])
        prompt = (cand["request"] + f"\n\nReference documents:\n\n{corpus}"
                  + "\n\nCompute the design yourself. Reply with ONE JSON object only, keys exactly these Results rows, values your computed results: " + json.dumps(rows))
        out[q] = []
        for i in range(N):
            try:
                resp = await client.chat(function=FUNCTION, model=MODEL, system_prompt="You are a careful senior engineer.", user_message=prompt, max_tokens=MAX_TOKENS)
                t = resp.content or ""
                obj = json.loads(t[t.find("{"):t.rfind("}") + 1]) if "{" in t else {"_error": "no JSON"}
            except Exception as exc:
                obj = {"_error": f"{type(exc).__name__}: {exc}"[:200]}
            out[q].append(obj)
            print(q, i + 1, {k: obj.get(k) for k in KEY_ROWS[q]} if "_error" not in obj else obj, flush=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    path = ROOT / f"evals/results/{stamp}-recompute-vote-samples.json"
    json.dump({"model": MODEL, "n": N, "samples": out, "spend": client.spend}, open(path, "w"), indent=1)
    print(f"spend ${client.spend:.4f}; samples {path}")


def score(samples_path, answers):
    """answers: list of (label, question, answer text, truth). Prints the flags."""
    s = json.load(open(samples_path))["samples"]
    for q in s:
        maj = {}
        for i, k in enumerate(KEY_ROWS[q]):
            maj[k] = majority([rc.find({kk: vv for kk, vv in smp.items() if not kk.startswith("_")}, k) for smp in s[q]], i == 0)
        print(f"{q} majority: {maj}")
        for label, qq, text, truth in answers:
            if qq != q:
                continue
            arows = rc.parse_table(text)
            diffs, none = [], []
            for i, k in enumerate(KEY_ROWS[q]):
                av, mv = rc.find(arows, k), maj[k]
                if mv is None:
                    none.append(k); continue
                if av is None:
                    continue
                if i == 0:
                    if rc.ident(av) != mv:
                        diffs.append((k, av, mv))
                elif rc.num(av) is not None and abs(rc.num(av) - mv) > rc.TOL * max(abs(mv), 1e-9):
                    diffs.append((k, rc.num(av), round(mv, 4)))
            print(f"   {label:36s} truth={truth:7s} flagged={bool(diffs)} diffs={diffs} no-consensus={none}")


if __name__ == "__main__":
    if sys.argv[1] == "sample":
        asyncio.run(sample())
