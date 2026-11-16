"""A reading aid for the run on the questions where a summary misleads. Free.

    python -I docs/probes/misleading_set_reading.py REPO OUT_PREFIX [QUESTION_ID]

OUT_PREFIX is the run's directories without the arm, e.g.
evals/results/20261115T-misleading (arms: now, documents, again). For each
question it prints the key and the figures commonly confused, then for every
answer of every arm: a pointer (which key figures and which confused figures
the answer's text holds), the delivery's cautions, and the sentences of the
answer that hold any of those figures. The pointer is not the result: the
answers are read against the keys by hand (D50).

With no QUESTION_ID it prints the totals only: units, completed, cost, the
pointer's count, cautions, and what the record says of the requests for
documents (how often the first was a miss, and of which kind).
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
PREFIX = sys.argv[2]
ONLY = sys.argv[3] if len(sys.argv) > 3 else None
SET = json.loads((REPO / "evals/professional/misleading-questions.json").read_text())
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers(text: str) -> list[str]:
    return list(dict.fromkeys(n.replace(",", "").rstrip(".") for n in NUMBER.findall(text)))


def holds(number: str, text: str) -> bool:
    return re.search(rf"(?<![\d.]){re.escape(number)}(?!\d|\.\d)",
                     text.replace(",", "")) is not None


for arm in ("now", "documents", "again"):
    units = [json.loads(line) for path in sorted(glob.glob(f"{PREFIX}-{arm}/shard-*.jsonl"))
             if "phases" not in path for line in open(path, encoding="utf-8")]
    phases = [json.loads(line) for path in sorted(glob.glob(f"{PREFIX}-{arm}/phases-shard-*.jsonl"))
              for line in open(path, encoding="utf-8")]
    total: Counter = Counter()
    for q in SET["questions"]:
        key = [n for item in q["key"] for n in numbers(item["answer"])]
        confused = [n for n in numbers(q.get("commonly_confused", "")) if n not in key]
        mine = [u for u in units if u.get("question") == q["id"]]
        if ONLY == q["id"]:
            print(f"\n##### {arm} {q['id']} key {[i['answer'] for i in q['key']]} "
                  f"| confused: {q.get('commonly_confused', '')[:160]}")
        for u in mine:
            total["units"] += 1
            total["cost"] += float(u.get("cost") or 0) + float(u.get("liability") or 0)
            if u.get("status") != "completed" or not u.get("answer"):
                total[f"status:{u.get('status')}"] += 1
                if ONLY == q["id"]:
                    print(f"  r{u.get('repeat')} {u.get('status')} {str(u.get('error'))[:120]}")
                continue
            total["completed"] += 1
            text = u["answer"]
            has_key = [n for n in key if holds(n, text)]
            has_confused = [n for n in confused if holds(n, text)]
            pointer = ("key" if len(has_key) == len(key) else "PART" if has_key else "NONE")
            total[f"pointer:{pointer}"] += 1
            total["no_caution"] += not u.get("cautions")
            total["cautions"] += len(u.get("cautions") or [])
            if ONLY == q["id"]:
                wanted = set(key) | set(confused)
                sentences = [s.strip() for s in re.split(r"(?<=[.;:])\s+|\n+", text)
                             if any(holds(n, s) for n in wanted)]
                print(f"  r{u['repeat']} {pointer} key{has_key} confused{has_confused} "
                      f"${u.get('cost')}")
                for c in u.get("cautions") or []:
                    print(f"      ! {c[:230]}")
                print("      " + " | ".join(sentences)[:520])
    # What the record says of the requests for documents.
    for row in phases:
        if row.get("kind") != "phase" or row.get("phase") != "sources":
            continue
        for finding in (row.get("verdict") or {}).get("findings") or []:
            documents = finding.get("documents") or []
            first = [d for d in documents if d.get("request") == 1]
            if not first:
                continue
            total["document_lookups"] += 1
            read = [d for d in first if d.get("read")]
            pointed = [d["holds_pointer"] for d in read if d.get("holds_pointer") is not None]
            if not read:
                total["miss:no_page_read"] += 1
            elif pointed and not any(pointed):
                total["miss:no_pointer_held"] += 1
            total["second_request_made"] += any(d.get("request") == 2 for d in documents)
            total["pages_named"] += len(first)
            total["pages_unread"] += len(first) - len(read)
    total["cost"] = round(total["cost"], 4)
    if ONLY is None:
        print(arm, dict(total))
