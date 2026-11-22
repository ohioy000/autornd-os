"""Score the hy4 arms by M1-M5 of docs/preregistration-triage-model-hy4-flash.md.
usage: score_hy4.py RESULTS_DIR PREFIX BASE   (PREFIX hy4 -> hy4-H0.. ; hy4on -> hy4on-T0..; names H0,Hg,Hf,Hm,Hl / T0,Tg,Tf,Tm,Tl)"""
import json, sys
from collections import Counter
from pathlib import Path
d, prefix, letter = Path(sys.argv[1]), sys.argv[2], sys.argv[3]   # letter H or T
MARGIN = 3
names = {"general (old text)": f"{letter}0", "general": f"{letter}g", "finance": f"{letter}f", "medical": f"{letter}m", "legal": f"{letter}l"}
def load(n):
    recs=[json.loads(l) for l in open(d/f"{prefix}-{n}.jsonl",encoding="utf-8")]
    return [r for r in recs if r.get("record")=="unit"]
def risk(u): return ((u.get("verdicts") or {}).get("triage") or {}).get("risk")
def stats(us):
    fl=bd=0
    for u in us:
        a={x["name"]:x["passed"] for x in u["assertions"]}
        fl+= (a.get("risk_at_least") is False); bd+=all(a.get(k,True) for k in ("risk_at_least","risk_at_most"))
    return fl,bd
def per(us):
    o={}
    for u in us: o.setdefault(u["scenario"],[]).append(risk(u))
    return o
def modal(r):
    c=Counter(r).most_common()
    return "tie" if len(c)>1 and c[0][1]==c[1][1] else c[0][0]
data={}
for lab,n in names.items():
    if (d/f"{prefix}-{n}.jsonl").exists():
        us=load(n)
        if len(us)>=140: data[n]=us
        else: print(f"(skip {n}: {len(us)} units)")
b=data.get(f"{letter}0")
print(f"{'arm':4} {'cost':>7} {'sec/unit':>8} {'errs':>4} {'floor<':>6} {'bounds':>6}  rule")
for n,us in data.items():
    f,bd=stats(us); errs=sum(1 for u in us if u.get("error") and "skipped" not in u["error"]); cost=sum(u.get("cost") or 0 for u in us); sec=sum(u["seconds"] for u in us)/len(us)
    if n==f"{letter}0": rule=f"M2 {'HOLDS' if f<=MARGIN and bd>=171 else 'FAILS'} (floor<={MARGIN}, bounds>=171)"
    elif n==f"{letter}g": rule=f"M3 {'holds' if f<=stats(b)[0]+MARGIN else 'FAILS'} | M4 {'HOLDS' if bd>=stats(b)[1]-MARGIN else 'FAILS'} (bounds>={stats(b)[1]-MARGIN})"
    else: rule=f"M3 {'HOLDS' if f<=stats(b)[0]+MARGIN else 'FAILS'} (floor<={stats(b)[0]+MARGIN})"
    print(f"{n:4} n={len(us):3} {cost:7.4f} {sec:8.1f} {errs:4} {f:6} {bd:6}  M1 {'holds' if errs<=2 else 'FAILS'} | {rule}")
if b:
    bs=per(b)
    for n,us in data.items():
        if n==f"{letter}0": continue
        s=per(us); mv=[(k,dict(Counter(bs[k])),dict(Counter(s[k]))) for k in sorted(bs) if modal(bs[k])!=modal(s[k])]
        un=[(k,bs[k][0],s[k][0]) for k in bs if len(set(bs[k]))==1 and len(set(s[k]))==1 and bs[k][0]!=s[k][0]]
        both=sum(1 for k in bs if len(set(bs[k]))==1 and len(set(s[k]))==1)
        print(f"== {n}: M5 modal movers {len(mv)}/36, unanimous-in-both {both}, differing {len(un)} {un}")
        for k,a,c in mv: print(f"   {k:26} {a} -> {c}")
