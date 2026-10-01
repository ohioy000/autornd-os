"""Advisor-written scorer for the golden set (ARCH-20261001-102). See SOURCE.md.

The executor uses this file and reports defects; it never edits it.
"""
import json, re, sys
from pathlib import Path
KEYS = Path(__file__).resolve().parent / "keys.json"
SUP = str.maketrans({"⁰":"0","¹":"1","²":"2","³":"3","⁴":"4","⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9","⁻":"-"})
def normalize(t):
    t = t.lower()
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
    s = k["side_test"]; t = normalize(s["model_answer"])
    core = {it["id"]: item_holds(it, t) for it in s["core_items"]}; sup = {it["id"]: item_holds(it, t) for it in s["supplementary_items"]}
    print("IA model answer core:", core, "| supplementary:", sup); bad += not all(core.values())
    root = KEYS.parent.parent.parent
    for v in k.get("regression_vectors", []):
        trace = root / v["trace"]
        if not trace.exists():
            # No evidence is never reported as no problem (convention 28): a
            # regression vector whose trace cannot be read fails the self-test.
            bad += 1; print(f"regression {v['scenario']}: BLIND (trace not found at {trace})"); continue
        recs = [json.loads(l) for l in open(trace, encoding="utf-8") if l.strip()]
        r = next(x for x in recs if x.get("scenario") == v["scenario"])
        q = next(q for q in k["golden"] if v["scenario"].endswith(q["id"].lower()[1:]) and q["id"] == "Q" + v["scenario"].split("_q")[-1])
        res = score(q, r["verdicts"]["implement"]["summary"]); ok = all(res.values()); bad += not ok
        print(f"regression {v['scenario']}: {'ALL HOLD' if ok else 'FAILS ' + str([i for i, x in res.items() if not x])}")
    print("SELF-TEST", "PASSED" if bad == 0 else f"FAILED ({bad})"); sys.exit(1 if bad else 0)
