"""Advisor-written scorer for the golden set (ARCH-20261001-102). See SOURCE.md.

The executor uses this file and reports defects; it never edits it.
"""
import json, re, sys
from pathlib import Path
KEYS = Path(__file__).resolve().parent / "keys.json"
SUP = str.maketrans({"⁰":"0","¹":"1","²":"2","³":"3","⁴":"4","⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9","⁻":"-"})
TEX = {"times": "×", "cdot": "·", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "lt": "<", "gt": ">",
       "approx": "≈", "pm": "±", "pi": "π", "mu": "µ", "circ": "°", "degree": "°", "Omega": "Ω", "Delta": "Δ"}
def delatex(t):
    # A key tests the figure, never its markup. 107's direct answers were
    # correct and failed on notation alone: '6.14 \times 10^{-7} \text{ m}^4',
    # '20.4 \text{ MPa}', '60.0 \text{ mm}^2', '30,000 \text{ mm}^3'. LaTeX
    # is reduced to the plain text it typesets, before every other step.
    t = re.sub(r"\\(?:text|mathrm|mathbf|mathit|textbf|textit|operatorname|mbox)\s*\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", t)
    t = re.sub(r"\\(?:left|right)(?![A-Za-z])", "", t)
    t = t.replace("\\%", "%")
    t = re.sub(r"\\[,;:! ]", " ", t)
    t = re.sub(r"\\([A-Za-z]+)", lambda m: TEX.get(m.group(1), m.group(0)), t)
    t = re.sub(r"\\[()\[\]]|\$", " ", t)
    return t.replace("{", "").replace("}", "")
def normalize(t):
    t = delatex(t).lower()
    t = re.sub(r"[−–—]", "-", t)
    t = t.replace("×", "x")
    t = re.sub(r"([⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda m: "^" + m.group(1).translate(SUP), t)
    t = t.replace("**", "").replace("`", "")
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    return re.sub(r"\s+", " ", t)
def item_holds(item, text):
    return all(re.search(p, text) for p in item["all"]) and not any(re.search(p, text) for p in item["none"])
def order_holds(patterns, text):
    # Sequence semantics: each pattern must match after the previous match.
    # A mention in a preamble or an equipment table must not count against the
    # order (102's Q5 exhibit: 'release valve' listed in a table above step 1).
    pos = 0
    for p in patterns:
        m = re.compile(p).search(text, pos)
        if not m: return False
        pos = m.end()
    return True
def score(q, answer, items_key="items"):
    t = normalize(answer)
    res = {it["id"]: item_holds(it, t) for it in q[items_key]}
    if "order" in q: res["ORDER"] = order_holds(q["order"], t)
    return res
if __name__ == "__main__":
    k = json.load(open(KEYS, encoding="utf-8")); bad = 0
    for q in k["golden"]:
        r = score(q, q["model_answer"])
        ok = all(r.values()); bad += not ok
        print(f"{q['id']} model answer: {'ALL HOLD' if ok else 'FAILS ' + str([i for i,v in r.items() if not v])}")
        for w in q["wrong"]:
            r = score(q, w["text"]); target = w["fails"]
            caught = (r.get(target) is False)
            others = [i for i, v in r.items() if not v and i != target]
            bad += not caught
            print(f"   wrong->{target}: {'caught' if caught else 'NOT CAUGHT'}" + (f" (also fails {others})" if others else ""))
        # SOURCE.md promised this from the start; until 2026-10-02 it was not run.
        for v in q.get("variants_must_pass", []):
            r = score(q, v); ok = all(r.values()); bad += not ok
            print(f"   variant: {'ALL HOLD' if ok else 'FAILS ' + str([i for i, x in r.items() if not x])}")
    s = k["side_test"]; t = normalize(s["model_answer"])
    core = {it["id"]: item_holds(it, t) for it in s["core_items"]}; sup = {it["id"]: item_holds(it, t) for it in s["supplementary_items"]}
    print("IA model answer core:", core, "| supplementary:", sup); bad += not all(core.values())
    for w in s.get("wrong", []):   # the side test's observed wrong forms (106, 107)
        r = {it["id"]: item_holds(it, normalize(w["text"])) for it in s["core_items"]}
        caught = r.get(w["fails"]) is False; bad += not caught
        print(f"   IA wrong->{w['fails']}: {'caught' if caught else 'NOT CAUGHT'}")
    for v in s.get("variants_must_pass", []):
        r = {it["id"]: item_holds(it, normalize(v)) for it in s["core_items"]}; ok = all(r.values()); bad += not ok
        print(f"   IA variant: {'ALL HOLD' if ok else 'FAILS ' + str([i for i, x in r.items() if not x])}")
    root = KEYS.parent.parent.parent
    for v in k.get("regression_vectors", []):
        trace = root / v["trace"]
        label = f"{trace.stem} {v.get('scenario') or v.get('id')}"
        if not trace.exists():
            # No evidence is never reported as no problem (convention 28): a
            # regression vector whose trace cannot be read fails the self-test.
            bad += 1; print(f"regression {label}: BLIND (trace not found at {trace})"); continue
        recs = [json.loads(l) for l in open(trace, encoding="utf-8") if l.strip()]
        if "scenario" in v:   # a harness run: the shipped implement summary
            r = next(x for x in recs if x.get("scenario") == v["scenario"])
            qid, text = "Q" + v["scenario"].split("_q")[-1], r["verdicts"]["implement"]["summary"]
        else:                 # a direct-call record (107): the answer text
            r = next(x for x in recs if x.get("record") == "answer" and x.get("id") == v["id"])
            qid, text = v["id"], r["answer"]
        q = next(q for q in k["golden"] if q["id"] == qid)
        res = score(q, text); ok = all(res.values()); bad += not ok
        print(f"regression {label}: {'ALL HOLD' if ok else 'FAILS ' + str([i for i, x in res.items() if not x])}")
    print("SELF-TEST", "PASSED" if bad == 0 else f"FAILED ({bad})"); sys.exit(1 if bad else 0)
