import asyncio, json, os, sys
sys.path.insert(0, os.getcwd())
from autornd.knowledge import absence
from autornd.knowledge.fetch import fetch_source
SP=os.environ["SP"]
cmp=json.load(open(SP+"/absence_words.json"))["results"]
codes=json.load(open(SP+"/packets-v2/codes.json"))
by={(r["q"],r["ask"]):r for r in cmp if "ask" in r and r["claimed_none"]}
def proofs_of(q):
    out=[]
    for code,m in codes.items():
        if m["question"]!=q or not m["delivered"]: continue
        s,n=m["source"].rsplit("#",1); d=os.path.dirname(s)
        ph=[json.loads(l) for l in open(d+"/phases-shard-0.jsonl")]
        w=[x for x in ph if x["kind"]=="workflow"][int(n)]
        for p in ph:
            if p["kind"]=="phase" and p["workflow_id"]==w["id"] and p["phase"]=="sources":
                for f in p["verdict"].get("findings") or []:
                    for pr in f.get("proofs") or []: out.append((pr["ask"],pr["url"]))
    return sorted(set(out))
async def main():
    for q in sorted({k[0] for k in by}):
        pairs=proofs_of(q)[:14]; urls=sorted({u for _,u in pairs})
        pages=await asyncio.gather(*(fetch_source(u) for u in urls)); read={u:p for u,p in zip(urls,pages) if p.fetched}
        for ask in sorted({a for (qq,a) in by if qq==q}):
            r=by[(q,ask)]
            ours=absence.prove({ask:absence.clean_terms(r["ours"])},read); theirs=absence.prove({ask:absence.clean_terms(r["stronger"])},read)
            only_ours={p.url for p in ours}-{p.url for p in theirs}
            print(f"{q} ask {ask}: pages read {len(read)} of {len(urls)}; proofs with our words {len(ours)}, with the stronger model's {len(theirs)}; pages where only ours proves absence: {[u[:60] for u in only_ours]}", flush=True)
asyncio.run(main())
