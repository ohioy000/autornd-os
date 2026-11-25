"""Free replay of the edition check over stored runs (2026-11-25). Run build.py-style extraction first; see docs/proposals/2026-11-25-edition-check.md.
build: proofs from every stored run DB, labelled by whether the frozen key says none; fetch: each proof page read again with fetch_source; rule: a year the request names and the ask's words repeat must be on the page.'"""
# --- build.py ---
import sqlite3,json,glob,re,asyncio,sys
sys.path.insert(0,"/home/jb/autornd-os-wt-pq")
E="/home/jb/autornd-os/evals/professional/"
Q={}
for f in ["holdout-questions.json","holdout2-questions.json","hard-questions.json","misleading-questions.json","questions.json"]:
    try: d=json.load(open(E+f))
    except Exception: continue
    for q in d["questions"]: Q[q["question"][:80]]=(f[:8]+":"+q["id"],q)
def none_key(q):
    k=q.get("key") or []
    return any(re.match(r"\s*(none|no |not stated|the document states none)",str(i.get("answer","")),re.I) for i in k)
rows={}
for db in glob.glob("/home/jb/final-runs/**/shard-*.db",recursive=True):
    try: c=sqlite3.connect(db)
    except Exception: continue
    try:
        wf={i:r for i,r in c.execute("select id,request from workflows")}
    except Exception: continue
    for wid,vj in c.execute("select workflow_id,verdict_json from phase_results where phase='sources'"):
        try: v=json.loads(vj)
        except Exception: continue
        req=wf.get(wid,""); m=Q.get(req[:80])
        if not m or not isinstance(v,dict): continue
        qid,q=m; legit=none_key(q)
        for f in v.get("findings",[]):
            for p in f.get("proofs") or []:
                k=(qid,p["ask"],p["url"])
                rows[k]=dict(qid=qid,ask=p["ask"],url=p["url"],chars=p["chars"],terms=p["terms"],request=req,legit=legit)
json.dump(list(rows.values()),open("proofs.json","w"))
print(len(rows),"proofs;",sum(r["legit"] for r in rows.values()),"on none-keyed questions;",len({r['url'] for r in rows.values()}),"urls;",len({r['qid'] for r in rows.values()}),"questions")

# --- fetch_all.py ---
import json,asyncio,sys
sys.path.insert(0,"/home/jb/autornd-os-wt-pq")
from autornd.knowledge.fetch import fetch_source
urls=sorted({r["url"] for r in json.load(open("proofs.json"))})
out={}
async def one(u,sem):
    async with sem:
        s=await fetch_source(u)
        out[u]=dict(status=s.status,reason=s.reason,text=s.text if s.fetched else "")
async def main():
    sem=asyncio.Semaphore(8)
    await asyncio.gather(*(one(u,sem) for u in urls))
asyncio.run(main()); json.dump(out,open("pages.json","w"))
print(len(out),sum(v["status"]=="fetched" for v in out.values()),"fetched")

# --- the rule ---
import json, re
yr = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")
def edition_missing(request, terms, page_text):
    named = set(yr.findall(request)) & set(yr.findall(" ".join(terms)))
    return named - set(yr.findall(page_text))
