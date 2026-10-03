"""Derive the tier-2 dataset's separated forms from the raw candidate export.

The owner's tier-2 command requires the dataset to separate
(1) model-visible requests, (2) reference source documents, and
(3) scorer-only keys, worked answers, and wrong-answer examples.
The candidate arrived as an orpg.3.0 chat export whose final
assistant message carries the question array as a JSON string.
This script reads that export verbatim and writes:

- questions.json  the model-visible requests (id, shape, domain,
  question) - what every arm's model sees;
- keys.json       the scorer-only material (required_items with
  values, tolerances and derivations/sources, scope_in,
  scope_out, common_wrong_answers, model_answer) - what no arm's
  model may see;
- manifest.json   the dataset record: versions, counts, the
  source archive, and the open items that block freezing.

Run:  .venv/bin/python3 evals/tier2/extract_candidate.py
Idempotent. No network, no provider calls.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "candidate" / "25GoldenQuestion.json"
PDF_PATH = HERE / "sources" / "CFR-2014-title29-vol5-sec1910-146.pdf"
TEXT_PATH = HERE / "sources" / "CFR-2014-title29-vol5-sec1910-146.txt"
ECFR_PATH = HERE / "sources" / "ecfr-current-2026-10-01-sec1910-146.xml"

DATASET_VERSION = "candidate-2026-10-03.2"
SCORER_VERSION = "candidate-2026-10-03.2"

# The count discrepancy that blocks freezing: the owner's command
# and its $90.00 aggregate ceiling arithmetic are written for a
# 25-question set; the supplied candidate array holds 5.
COMMAND_EXPECTED_COUNT = 25


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# The five shapes the owner's command defines (plus OWNER,
# the shape the command assigns to keys of owner-pasted
# questions). The export's first assistant turn answers the
# schema prompt with a `clarification` object that echoes
# the same field names; the shape vocabulary is what
# distinguishes a real question from that exchange.
QUESTION_SHAPES = {
    "SANITY", "LOOKUP", "DERIVATION", "SPECIFICATION",
    "PROCEDURE", "OWNER",
}


def load_question_array() -> list[dict]:
    """Find the final assistant message item that parses as the
    question array, and return it. The export's structure: an
    assistant message whose items include a `message` item whose
    first content block is a JSON array of question objects."""
    export = json.loads(RAW.read_text())
    candidates = []
    for message in export["messages"].values():
        if message.get("type") != "assistant":
            continue
        for stub in message.get("items", []):
            # Items are either string references into the
            # export's items table or inline stubs that carry
            # the same id; both resolve there.
            item_id = stub if isinstance(stub, str) else stub.get("id")
            if not isinstance(item_id, str):
                continue
            item = export["items"].get(item_id, {}).get("data", {})
            if item.get("type") != "message":
                continue
            for block in item.get("content", []):
                text = block.get("text", "")
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if (
                    isinstance(parsed, list)
                    and parsed
                    and all(
                        isinstance(q, dict)
                        and {"id", "shape", "domain", "question",
                             "required_items", "model_answer"}
                        <= set(q)
                        and q["shape"] in QUESTION_SHAPES
                        for q in parsed
                    )
                ):
                    candidates.append(parsed)
    if len(candidates) != 1:
        raise SystemExit(
            f"expected exactly one question array in the export, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def main() -> None:
    questions = load_question_array()
    raw_hash = sha256_file(RAW)

    model_visible = [
        {
            "id": q["id"],
            "shape": q["shape"],
            "domain": q["domain"],
            "question": q["question"],
        }
        for q in questions
    ]
    scorer_only = [
        {
            "id": q["id"],
            "required_items": q["required_items"],
            "sources": q["sources"],
            "scope_in": q["scope_in"],
            "scope_out": q["scope_out"],
            "common_wrong_answers": q["common_wrong_answers"],
            "model_answer": q["model_answer"],
        }
        for q in questions
    ]

    (HERE / "questions.json").write_text(
        json.dumps(model_visible, indent=2) + "\n"
    )
    (HERE / "keys.json").write_text(
        json.dumps(scorer_only, indent=2) + "\n"
    )

    manifest = {
        "dataset_version": DATASET_VERSION,
        "scorer_version": SCORER_VERSION,
        "frozen": False,
        "freeze_blocked_by": [
            "count-discrepancy: the owner's command and its $90.00 "
            "aggregate ceiling are written for a 25-question set; "
            "the supplied candidate array holds "
            f"{len(questions)}. The remaining "
            f"{COMMAND_EXPECTED_COUNT - len(questions)} questions "
            "must be supplied by the owner or advisor - the tier-2 "
            "command forbids the executor (and any AI model) from "
            "generating, screening, or selecting questions."
        ],
        "candidate": {
            "file": "candidate/25GoldenQuestion.json",
            "bytes": RAW.stat().st_size,
            "sha256": raw_hash,
            "format": "orpg.3.0 chat export; the question array is "
                      "the final assistant message's output_text",
            "supplied_by": "owner, in conversation, 2026-10-03",
        },
        "questions": len(questions),
        "command_expected_questions": COMMAND_EXPECTED_COUNT,
        "shapes": sorted({q["shape"] for q in questions}),
        "domains": [q["domain"] for q in questions],
        "separation": {
            "model_visible_requests": "questions.json",
            "reference_source_documents": "sources/",
            "scorer_only_keys_and_worked_answers": "keys.json",
        },
        "source_archives": [
            {
                "question": "Q2",
                "edition": "29 CFR, Title 29, July 1, 2014 edition, "
                           "section 1910.146",
                "edition_basis": "The section PDF starts "
                                 "mid-standard and carries no "
                                 "volume title page; the edition "
                                 "is identified by the govinfo "
                                 "package identifier "
                                 "(CFR-2014-title29-vol5 = the "
                                 "annual edition of Title 29, "
                                 "volume 5, revised as of July 1) "
                                 "and corroborated by the GPO "
                                 "typesetting date in every page "
                                 "footer (Aug 01, 2014, file "
                                 "29V5.TXT).",
                "url": "https://www.govinfo.gov/content/pkg/"
                       "CFR-2014-title29-vol5/pdf/"
                       "CFR-2014-title29-vol5-sec1910-146.pdf",
                "retrieved_utc": "2026-10-03T07:59:27Z",
                "file": "sources/CFR-2014-title29-vol5-sec1910-146.pdf",
                "bytes": PDF_PATH.stat().st_size,
                "sha256": sha256_file(PDF_PATH),
                "text_extraction": "sources/"
                                   "CFR-2014-title29-vol5-sec1910-146.txt",
                "text_bytes": TEXT_PATH.stat().st_size,
                "text_sha256": sha256_file(TEXT_PATH),
                "text_extraction_tool": "pdftotext -layout "
                                        "(Poppler); the committed "
                                        ".txt is the hermetic test "
                                        "input",
            },
            {
                "what": "Stability cross-check: the two oxygen "
                        "definitions in paragraph (b) are identical "
                        "in the pinned July 1, 2014 annual edition "
                        "and in the current eCFR text as of "
                        "2026-10-01, fetched via the eCFR versioner "
                        "API - a 12-year span, which satisfies the "
                        "command's 'unchanged for at least three "
                        "years' requirement for lookup sources.",
                "url": "https://www.ecfr.gov/api/versioner/v1/full/"
                       "2026-10-01/title-29.xml?part=1910"
                       "&section=1910.146",
                "retrieved_utc": "2026-10-03T08:05:53Z",
                "file": "sources/"
                        "ecfr-current-2026-10-01-sec1910-146.xml",
                "bytes": ECFR_PATH.stat().st_size,
                "sha256": sha256_file(ECFR_PATH),
            }
        ],
    }
    (HERE / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(f"questions: {len(questions)} (command expects "
          f"{COMMAND_EXPECTED_COUNT} - NOT frozen)")
    print(f"candidate sha256: {raw_hash}")
    for q in questions:
        print(f"  {q['id']} {q['shape']:<11} {q['domain']}")


if __name__ == "__main__":
    main()
