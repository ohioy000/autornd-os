"""Point the reading of the professional set's baseline. Free.

    python docs/probes/professional_baseline_analysis.py REPO DIR PREFIX

DIR holds PREFIXshard-N.jsonl (one answer a line) and PREFIXphases-shard-N.jsonl
(the run rows). For each answer it prints: whether every figure of each key
item is in the answer's text; whether a quote found on its page holds every
figure of the key's passage; the quotes by status and site; the cautions.
The figure check is a pointer for the reader, never the result (D50).
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter

REPO, ROOT, PREFIX = sys.argv[1], sys.argv[2], sys.argv[3]
KEYS = {q["id"]: q for name in ("questions.json", "hard-questions.json")
        for q in json.load(open(f"{REPO}/evals/professional/{name}"))["questions"]}
for _q in KEYS.values():   # the hard set gives several sources a question
    _q.setdefault("passage", " ".join(s["passage"] for s in _q.get("sources", [])))
FIGURE = re.compile(r"\d[\d.,/]*\d|\d")


def squash(text: str) -> str:
    return re.sub(r"[\s*_`$\\{}]|mathrm|text|,", "", text).casefold()


def figures(text: str) -> list[str]:
    return [f.replace(",", "") for f in FIGURE.findall(text)]


total: Counter = Counter()
for path in sorted(glob.glob(f"{ROOT}/{PREFIX}shard-*.jsonl")):
    if "phases-" in path:
        continue
    records = [json.loads(line) for line in open(path, encoding="utf-8")]
    rows = [json.loads(line) for line in open(
        path.replace(f"{PREFIX}shard-", f"{PREFIX}phases-shard-"), encoding="utf-8")]
    ids = [r["id"] for r in rows if r["kind"] == "workflow"]
    for wid, record in zip(ids, records):
        key = KEYS[record["question"]]
        answer = squash(record.get("answer") or "")
        missing = [item["item"] for item in key["key"] if not item.get("derived")
                   if not all(squash(f) in answer for f in figures(item["answer"]))]
        findings = [f for r in rows if r["kind"] == "phase"
                    and r["workflow_id"] == wid and r["phase"] == "sources"
                    for f in r["verdict"].get("findings") or []]
        quotes = [q for f in findings for q in f.get("quotes") or []]
        found = " ".join(q["text"] for q in quotes if q["status"] == "found")
        quoted = " ".join(q["text"] for q in quotes)
        want = figures(key["passage"])
        passage_found = bool(found) and all(squash(f) in squash(found) for f in want)
        passage_quoted = bool(quoted) and all(squash(f) in squash(quoted) for f in want)
        vote = record.get("recompute_vote") or {}
        compared = bool(vote.get("checked")) and not vote.get("unchecked")
        total["answers"] += 1
        total["all_figures_in_answer"] += not missing
        total["passage_found"] += passage_found
        total["passage_quoted"] += passage_quoted
        total["lookup_ran"] += bool(findings)
        total["vote_compared"] += compared
        total["vote_flagged"] += bool(vote.get("flagged"))
        total["status_" + str(record["status"])] += 1
        total["quotes"] += len(quotes)
        for q in quotes:
            total["q_" + q["status"]] += 1
        total["cost"] += record["cost"]
        sites = Counter(q["status"][:5] + ":" + q["url"].split("/")[2].replace("www.", "")
                        for q in quotes)
        print(record["question"], record["repeat"], record["status"],
              "figures ok" if not missing else f"MISSING {missing}",
              "| passage found" if passage_found else
              "| passage quoted, not found" if passage_quoted else "| passage not quoted",
              "| vote compared" if compared else "| vote compared nothing",
              "flagged" if vote.get("flagged") else "",
              "|", dict(sites), "| cautions", len(record.get("cautions") or []),
              "| $", record["cost"])
total["cost"] = round(total["cost"], 3)
print(dict(total))
