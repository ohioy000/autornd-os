"""The words a proof of absence searches for, made with thinking off by the triage tier, against the same prompt answered by a stronger model
at its default thinking. One capped probe, 2026-11-23 (the owner asked after the proofs started to be made).

    python docs/probes/absence_words_comparison.py RUNS_DIR CODES_JSON OUT_JSON [MAX_QUESTIONS] [CEILING]

RUNS_DIR is /home/jb/final-runs; CODES_JSON the revised caution fix's test codes (caution_v2_packets.py). For each of the questions chosen (every
question whose answer used the "not stated" channel, then a seeded sample of the others) the stored words of the run are read from its
sources rows, the stronger model (the architecture tier) is asked the same prompt, and the two lists are compared after the proof's own
folding (`absence._flat`): how many of the stronger model's words the run's list holds exactly, and how many it holds in a longer or a
shorter form. Spend is counted and the probe stops at CEILING. The tree must be the revised caution branch (`autornd.knowledge.absence`).
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
from autornd.knowledge import absence  # noqa: E402
from autornd.routing.openrouter import OpenRouterClient, check_models  # noqa: E402

RUNS = Path(sys.argv[1])
CODES = json.loads(Path(sys.argv[2]).read_text())
OUT = Path(sys.argv[3])
MAXQ = int(sys.argv[4]) if len(sys.argv) > 4 else 30
CEILING = float(sys.argv[5]) if len(sys.argv) > 5 else 0.40


def load(source: str):
    path, n = source.rsplit("#", 1)
    rows = [json.loads(x) for x in open(Path(path).parent / "phases-shard-0.jsonl", encoding="utf-8")]
    wf = [r for r in rows if r["kind"] == "workflow"][int(n)]
    phases = sorted((r for r in rows if r["kind"] == "phase" and r["workflow_id"] == wf["id"]), key=lambda r: r["created_at"])
    asks = [a for r in phases if r["phase"] == "asks" for a in r["verdict"]["asks"]]
    searched: dict[str, list] = {}
    for r in phases:
        if r["phase"] == "sources":
            for f in r["verdict"].get("findings") or []:
                for k, v in (f.get("searched") or {}).items():
                    searched.setdefault(k, v)
    impl = [r["verdict"] for r in phases if r["phase"] == "implement"]
    claimed = bool(impl and impl[-1].get("not_stated"))
    return wf["request"], asks, searched, claimed


units = {}
for code, m in CODES.items():
    if not m["delivered"]:
        continue
    key = (m["set"], m["question"])
    request, asks, searched, claimed = load(m["source"])
    u = units.setdefault(key, {"code": code, "request": request, "asks": asks, "searched": searched, "claimed": False})
    u["claimed"] = u["claimed"] or claimed
    if not u["searched"]:
        u["searched"] = searched
chosen = [k for k, u in sorted(units.items()) if u["claimed"]]
rest = sorted(k for k in units if k not in chosen)
random.Random("absence-words-20261123").shuffle(rest)
chosen = (chosen + rest)[:MAXQ]


def fold(term: str) -> str:
    return absence._flat(absence._fold(term))


async def main() -> None:
    await check_models()
    client = OpenRouterClient()
    spent, out = 0.0, []
    for key in chosen:
        if spent >= CEILING:
            print("ceiling reached; stopped"); break
        u = units[key]
        anchored = [dict(number=i, quote=a["quote"], kind=a["kind"]) for i, a in enumerate(u["asks"], 1)]
        wanted = absence.provable_asks(anchored)
        if not wanted:
            continue
        listing = "\n".join(f"{n}. {q}" for n, q in sorted(wanted.items()))
        try:
            data, resp = await client.chat_json(
                function="architecture", system_prompt="You list the words a document uses for what a question asks. Respond with JSON only.",
                user_message=absence.TERMS_PROMPT.format(request=u["request"], asks=listing),
                temperature=0.0, max_tokens=6000, schema=absence.TermsVerdict)
            spent = float(getattr(client, "spend", spent) or spent)
            strong = {e.ask: absence.clean_terms(e.any_of) for e in absence.TermsVerdict(**data).terms}
        except Exception as exc:  # recorded, not hidden
            out.append({"set": key[0], "q": key[1], "error": f"{type(exc).__name__}: {str(exc)[:160]}"}); continue
        for ask in sorted(wanted):
            ours = u["searched"].get(str(ask)) or []
            theirs = strong.get(ask) or []
            fo, ft = [fold(t) for t in ours], [fold(t) for t in theirs]
            exact = sum(t in fo for t in ft)
            contained = sum(any(t in o or o in t for o in fo if o and t) and t not in fo for t in ft)
            out.append({"set": key[0], "q": key[1], "ask": ask, "claimed_none": u["claimed"], "ours": ours, "stronger": theirs,
                        "stronger_exact_in_ours": exact, "stronger_in_longer_or_shorter_form": contained,
                        "stronger_missing_from_ours": [t for t, f in zip(theirs, ft) if f not in fo]})
    OUT.write_text(json.dumps({"spend": round(spent, 4), "results": out}, indent=1, ensure_ascii=False))
    asks_ = [r for r in out if "ask" in r and r["stronger"]]
    n_t = sum(len(r["stronger"]) for r in asks_)
    print(f"questions {len(chosen)}, asks compared {len(asks_)}, the stronger model's words {n_t}: held exactly "
          f"{sum(r['stronger_exact_in_ours'] for r in asks_)}, held in a longer or shorter form "
          f"{sum(r['stronger_in_longer_or_shorter_form'] for r in asks_)}, absent from the run's list "
          f"{sum(len(r['stronger_missing_from_ours']) for r in asks_) - sum(r['stronger_in_longer_or_shorter_form'] for r in asks_)}; "
          f"asks where the run's list had no words {sum(not r['ours'] for r in asks_)}; spend ${spent:.4f}")
    await client.close()


asyncio.run(main())
