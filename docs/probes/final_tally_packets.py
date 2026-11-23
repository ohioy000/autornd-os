"""Write the final tally's blind reading packets. Free.

    python -I final_tally_packets.py REPO OUT_DIR SEED [FIRST_DIR [RESUME_DIR]]

One packet per question (docs/preregistration-20261123-final-tally.md and its amendment 1): the question, its signed key
(for tier 4, its requirement statements with the reference design and the catalogue pages) and every delivered answer of
the question under a code that shows neither the arm, nor the run, nor the invocation, in a shuffled order. For the 56
field questions the packet holds the answer on the field profile (arm F, the tally's own) and the one on the engineering
profile (arm E, the small test) together, so the reader cannot tell which is which. The codes, with where each answer came
from, are kept in OUT_DIR/codes.json, which the reader is not given. A unit that delivered no answer is listed in
codes.json and not in a packet.

It also writes OUT_DIR/chunks-items.json and OUT_DIR/chunks-tier4.json: the packet files split into lists of about the
same number of answers, one list a reader (`--per-reader` in the environment, READ_PER, default 30 answers).
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import final_tally_launch as launch  # noqa: E402  (the plan: which invocation holds which questions, on which profile)

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
SEED = sys.argv[3]
FIRST = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("/home/jb/final-runs")
RESUME = Path(sys.argv[5]) if len(sys.argv) > 5 else FIRST / "resume1"
PER_READER = int(os.environ.get("READ_PER", "30"))
OUT.mkdir(parents=True, exist_ok=True)


def load_json(path: str):
    return json.loads((REPO / path).read_text(encoding="utf-8"))


# ---- the keys, by set -------------------------------------------------------------------------------------------------
PRO = {"professional": "questions.json", "professional-hard": "hard-questions.json",
       "professional-misleading": "misleading-questions.json", "professional-holdout": "holdout-questions.json",
       "professional-holdout-2": "holdout2-questions.json"}
PRO_Q: dict[str, dict[str, dict]] = {s: {q["id"]: q for q in load_json(f"evals/professional/{f}")["questions"]}
                                     for s, f in PRO.items()}
T2_Q = {q["id"]: q for q in load_json("evals/tier2/questions.json")}
T2_K = {k["id"]: k for k in load_json("evals/tier2/keys.json")}
GOLD = load_json("evals/golden/keys.json")
GOLD_Q = {g["id"]: g for g in GOLD["golden"]}
GOLD_Q[GOLD["side_test"]["id"]] = GOLD["side_test"]
T4_Q: dict[str, dict] = {}
for _batch in ("pilot", "batch2", "batch3", "batch4", "batch5", "batch6"):
    for _c in load_json(f"evals/tier4/{_batch}/candidates.json"):
        T4_Q[_c["id"]] = _c


def block_professional(set_name: str, qid: str) -> list[str]:
    q = PRO_Q[set_name][qid]
    lines = [f"**Question:** {q['question']}", "", "**Key (signed):**"]
    lines += [f"- {item['item']}: {item['answer']}" for item in q["key"]]
    lines += ["", f"**Commonly confused:** {q.get('commonly_confused', '')}"]
    return lines


def block_tier2(qid: str) -> list[str]:
    q, k = T2_Q[qid], T2_K[qid]
    lines = [f"**Question:** {q['question']}", "", "**Key (signed), every item is required:**"]
    for item in k["required_items"]:
        lines.append(f"- {item['item']}: {item['value']}")
        lines.append(f"  - accept: {item.get('tolerance_or_variants', '')}")
        lines.append(f"  - derivation: {item.get('derivation_or_source', '')}")
    wrong = k.get("common_wrong_answers") or []
    lines += ["", "**Commonly confused:** " + " | ".join(f"{w['answer']} ({w['why_wrong']})" for w in wrong)]
    lines += ["", f"**Model answer:** {k.get('model_answer', '')}"]
    return lines


def block_golden(qid: str) -> list[str]:
    g = GOLD_Q[qid]
    items = g.get("items") or g.get("core_items") or []
    lines = [f"**Question:** {g['request']}", "", f"**Where the key comes from:** {g['source']}", "",
             "**Key, every item is required:**"]
    lines += [f"- {item['item']}" for item in items]
    if g.get("supplementary_items"):
        lines += ["", "**Supplementary (not required, noted only):**"]
        lines += [f"- {item['item']}" for item in g["supplementary_items"]]
    if g.get("model_answer"):
        lines += ["", f"**Model answer:** {g['model_answer']}"]
    return lines


def block_tier4(qid: str) -> list[str]:
    c = T4_Q[qid]
    lines = [f"**Request (what the system was given, with the catalogue pages below in the message):** {c['request']}", "",
             "**Requirements (the answer is right only when EVERY requirement is met):**"]
    for r in c["requirements"]:
        lines.append(f"- {r['id']}: {r['statement']}  [method: {r.get('method') or r.get('check', '')}; "
                     f"tolerance: {r.get('tolerance', '')}]")
    lines += ["", f"**Reference design:** {json.dumps(c.get('reference_design'), ensure_ascii=False)}", "",
              f"**Worked solution:** {c.get('worked_solution', '')}", "",
              "**Designs known to fail (what a missed trap looks like):**"]
    for w in c.get("wrong_designs") or []:
        lines.append(f"- {json.dumps(w.get('values'), ensure_ascii=False)} fails {w.get('failed_requirement_ids')}: {w.get('why', '')}")
    trap = c.get("trap") or {}
    lines += ["", f"**The trap:** {trap.get('judgment', '')}", "", "**Catalogue pages the system was given:**"]
    for page in c.get("corpus_pages") or []:
        lines += ["", f"### {page.get('title', '')}", page.get("markdown", "")]
    return lines


def packet_head(set_name: str, qid: str) -> tuple[str, list[str], str]:
    """The packet's file name, the question and key block, and which kind of reader reads it."""
    if set_name in PRO:
        return f"{set_name}__{qid}.md", block_professional(set_name, qid), "items"
    if set_name == "tier2":
        return f"tier2__{qid}.md", block_tier2(qid), "items"
    if set_name == "golden":
        return f"golden__{qid}.md", block_golden(qid), "items"
    if set_name == "tier4":
        return f"tier4__{qid}.md", block_tier4(qid), "tier4"
    raise SystemExit(f"unknown set {set_name}")


# ---- the units --------------------------------------------------------------------------------------------------------
def arm_of(name: str) -> str:
    return "E" if name.startswith("E-") else ("F" if name.startswith("F-") else "tally")


units: list[dict] = []
for lane in launch.lanes():
    for inv in lane:
        for run, root in (("first", FIRST), ("resume", RESUME)):
            path = root / inv["name"] / "shard-0.jsonl"
            if not path.exists():
                continue
            for n, line in enumerate(open(path, encoding="utf-8")):
                u = json.loads(line)
                u.update(_source=f"{path}#{n}", _run=run, _inv=inv["name"], _set=inv["set"], _arm=arm_of(inv["name"]))
                units.append(u)

codes: dict[str, dict] = {}
packets: dict[str, dict] = {}
for u in units:
    code = hashlib.sha256(f"{SEED}|{u['_source']}".encode()).hexdigest()[:8]
    answer = (u.get("answer") or "").strip()
    codes[code] = {"source": u["_source"], "set": u["_set"], "question": u["question"], "arm": u["_arm"],
                   "run": u["_run"], "invocation": u["_inv"], "status": u.get("status"),
                   "delivered": bool(answer), "error": (u.get("error") or "")[:160]}
    if answer:
        name, head, kind = packet_head(u["_set"], u["question"])
        p = packets.setdefault(name, {"head": head, "kind": kind, "set": u["_set"], "question": u["question"], "answers": []})
        p["answers"].append((code, answer))
(OUT / "codes.json").write_text(json.dumps(codes, indent=1), encoding="utf-8")

rng = random.Random(SEED)
for name in sorted(packets):
    p = packets[name]
    rng.shuffle(p["answers"])
    lines = [f"# {p['question']} ({p['set']})", ""] + p["head"] + ["", f"{len(p['answers'])} answer(s) follow.", ""]
    for code, answer in p["answers"]:
        lines += [f"## ANSWER {code}", "", answer, "", "---", ""]
    (OUT / name).write_text("\n".join(lines), encoding="utf-8")


def chunk(names: list[str]) -> list[list[str]]:
    """Packet files into lists of about PER_READER answers, in file order, no packet split."""
    out, cur, count = [], [], 0
    for name in names:
        n = len(packets[name]["answers"])
        if cur and count + n > PER_READER:
            out.append(cur)
            cur, count = [], 0
        cur.append(name)
        count += n
    if cur:
        out.append(cur)
    return out


for kind in ("items", "tier4"):
    names = [n for n in sorted(packets) if packets[n]["kind"] == kind]
    (OUT / f"chunks-{kind}.json").write_text(json.dumps(chunk(names), indent=1), encoding="utf-8")
delivered = sum(1 for c in codes.values() if c["delivered"])
print(f"units {len(codes)}  delivered answers {delivered}  packets {len(packets)}  "
      f"readers: items {len(chunk([n for n in sorted(packets) if packets[n]['kind'] == 'items']))}, "
      f"tier4 {len(chunk([n for n in sorted(packets) if packets[n]['kind'] == 'tier4']))}")
by_run = {}
for c in codes.values():
    by_run[(c["run"], c["arm"], c["delivered"])] = by_run.get((c["run"], c["arm"], c["delivered"]), 0) + 1
for k in sorted(by_run):
    print("  ", k, by_run[k])
