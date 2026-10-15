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
# Q7 and Q22 share one regulation (29 CFR 1910.95: Table G-16
# and paragraph (g)); Q12 reads 40 CFR 141.62(b); Q17 reads
# 29 CFR 1910.147(c)(5)(ii)(C)(2) and (c)(6)(i).
PDF_95_PATH = HERE / "sources" / "CFR-2014-title29-vol5-sec1910-95.pdf"
TEXT_95_PATH = HERE / "sources" / "CFR-2014-title29-vol5-sec1910-95.txt"
ECFR_95_PATH = HERE / "sources" / "ecfr-current-2026-10-01-sec1910-95.xml"
PDF_62_PATH = HERE / "sources" / "CFR-2014-title40-vol23-sec141-62.pdf"
TEXT_62_PATH = HERE / "sources" / "CFR-2014-title40-vol23-sec141-62.txt"
ECFR_62_PATH = HERE / "sources" / "ecfr-current-2026-10-01-sec141-62.xml"
PDF_147_PATH = HERE / "sources" / "CFR-2014-title29-vol5-sec1910-147.pdf"
TEXT_147_PATH = HERE / "sources" / "CFR-2014-title29-vol5-sec1910-147.txt"
ECFR_147_PATH = HERE / "sources" / "ecfr-current-2026-10-01-sec1910-147.xml"

DATASET_VERSION = "frozen-2026-10-03"
# The scorer's current version. The dataset froze
# at frozen-2026-10-03; the scorer repair Ruling
# D50 (1) orders (the recorded answers the frozen
# scorer failed) is a new version under the freeze,
# and the repair Ruling R5 orders (the tier-3
# stage-1 reading's recognition classes, the
# strict-headline rule and its bound-word guard)
# is a further one: the dataset content is
# unchanged, only the instrument changed.
SCORER_VERSION = "frozen-2026-10-03.3"

# The count the owner's command expects. The owner
# supplied all 25 on 2026-10-03, and ratified the
# tier-2 signoff the same day: the set is frozen.
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

    supplied = len(questions)
    if supplied == COMMAND_EXPECTED_COUNT:
        blockers = []
        freeze = {
            "signed_off_by": "owner",
            "signed_off_utc": "2026-10-03T21:41:20Z",
            "granted": ("in conversation: "
                        "'ratify the tier-2 signoff'"),
            "scope": ("the independent verification (all 268 "
                      "checks of verify_keys.py) and the source "
                      "review (four archived July 1, 2014 govinfo "
                      "editions with verbatim quotation matches and "
                      "2026-10-01 eCFR stability cross-checks) the "
                      "tier-2 command requires before the set "
                      "freezes and before paid use"),
            "effect": ("the dataset and scorer versions are frozen "
                       "at frozen-2026-10-03; paid use of the set "
                       "is permitted subject to the tier-3 command's "
                       "own ratification requirements "
                       "(ARCH-20261002-118)"),
        }
    else:
        blockers = [
            "count-discrepancy: the owner's command and its $90.00 "
            "aggregate ceiling are written for a 25-question set; "
            "the supplied candidate array holds "
            f"{supplied}. The remaining "
            f"{COMMAND_EXPECTED_COUNT - supplied} questions "
            "must be supplied by the owner or advisor - the tier-2 "
            "command forbids the executor (and any AI model) from "
            "generating, screening, or selecting questions."
        ]
        freeze = None
    manifest = {
        "dataset_version": DATASET_VERSION,
        "scorer_version": SCORER_VERSION,
        "frozen": freeze is not None,
        "freeze_blocked_by": blockers,
        "freeze": freeze,
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
            },
            {
                "question": "Q7, Q22",
                "edition": "29 CFR, Title 29, July 1, 2014 "
                             "edition, section 1910.95",
                "edition_basis": "The section PDF's first page "
                                 "carries the tail of the preceding "
                                 "section beside section 1910.95's "
                                 "opening paragraph; the edition is "
                                 "identified by the govinfo package "
                                 "identifier (CFR-2014-title29-vol5 "
                                 "= the annual edition of Title 29, "
                                 "volume 5, revised as of July 1) "
                                 "and corroborated by the GPO "
                                 "typesetting footer on every page "
                                 "('29 CFR Ch. XVII (7-1-14 "
                                 "Edition)').",
                "url": "https://www.govinfo.gov/content/pkg/"
                       "CFR-2014-title29-vol5/pdf/"
                       "CFR-2014-title29-vol5-sec1910-95.pdf",
                "retrieved_utc": "2026-10-03T09:44:53Z",
                "file": "sources/CFR-2014-title29-vol5-sec1910-95.pdf",
                "bytes": PDF_95_PATH.stat().st_size,
                "sha256": sha256_file(PDF_95_PATH),
                "text_extraction": "sources/"
                                   "CFR-2014-title29-vol5-sec1910-95.txt",
                "text_bytes": TEXT_95_PATH.stat().st_size,
                "text_sha256": sha256_file(TEXT_95_PATH),
                "text_extraction_tool": "pdftotext -layout "
                                        "(Poppler); the committed "
                                        ".txt is the hermetic test "
                                        "input",
            },
            {
                "what": "Stability cross-check: the Table G-16 "
                        "duration rows (8 hours at 90 dBA, 4 hours "
                        "at 95 dBA, 2 hours at 100 dBA, slow "
                        "response) and the paragraph (g) provisions "
                        "(baseline audiogram within 6 months, "
                        "at least 14 hours without workplace noise "
                        "before a baseline, retest within 30 days) "
                        "are identical in the pinned July 1, 2014 "
                        "annual edition and in the current eCFR text "
                        "as of 2026-10-01, fetched via the eCFR "
                        "versioner API - a 12-year span, which "
                        "satisfies the command's 'unchanged for at "
                        "least three years' requirement for lookup "
                        "sources.",
                "url": "https://www.ecfr.gov/api/versioner/v1/full/"
                       "2026-10-01/title-29.xml?part=1910"
                       "&section=1910.95",
                "retrieved_utc": "2026-10-03T09:47:06Z",
                "file": "sources/"
                        "ecfr-current-2026-10-01-sec1910-95.xml",
                "bytes": ECFR_95_PATH.stat().st_size,
                "sha256": sha256_file(ECFR_95_PATH),
            },
            {
                "question": "Q12",
                "edition": "40 CFR, Title 40, July 1, 2014 "
                             "edition, section 141.62",
                "edition_basis": "The edition is identified by the "
                                 "govinfo package identifier "
                                 "(CFR-2014-title40-vol23 = the "
                                 "annual edition of Title 40, volume "
                                 "23, revised as of July 1) and "
                                 "corroborated by the GPO typesetting "
                                 "footer on every page ('40 CFR Ch. I "
                                 "(7-1-14 Edition)').",
                "url": "https://www.govinfo.gov/content/pkg/"
                       "CFR-2014-title40-vol23/pdf/"
                       "CFR-2014-title40-vol23-sec141-62.pdf",
                "retrieved_utc": "2026-10-03T09:44:54Z",
                "file": "sources/CFR-2014-title40-vol23-sec141-62.pdf",
                "bytes": PDF_62_PATH.stat().st_size,
                "sha256": sha256_file(PDF_62_PATH),
                "text_extraction": "sources/"
                                   "CFR-2014-title40-vol23-sec141-62.txt",
                "text_bytes": TEXT_62_PATH.stat().st_size,
                "text_sha256": sha256_file(TEXT_62_PATH),
                "text_extraction_tool": "pdftotext -layout "
                                        "(Poppler); the committed "
                                        ".txt is the hermetic test "
                                        "input",
            },
            {
                "what": "Stability cross-check: the maximum "
                        "contaminant levels in paragraph (b) - "
                        "fluoride 4.0 mg/L ((b)(1)), nitrate 10 mg/L "
                        "as Nitrogen ((b)(7)), arsenic 0.010 mg/L "
                        "((b)(16)) - are identical in the pinned "
                        "July 1, 2014 annual edition and in the "
                        "current eCFR text as of 2026-10-01, fetched "
                        "via the eCFR versioner API - a 12-year span, "
                        "which satisfies the command's 'unchanged for "
                        "at least three years' requirement for lookup "
                        "sources.",
                "url": "https://www.ecfr.gov/api/versioner/v1/full/"
                       "2026-10-01/title-40.xml?part=141"
                       "&section=141.62",
                "retrieved_utc": "2026-10-03T09:47:11Z",
                "file": "sources/"
                        "ecfr-current-2026-10-01-sec141-62.xml",
                "bytes": ECFR_62_PATH.stat().st_size,
                "sha256": sha256_file(ECFR_62_PATH),
            },
            {
                "question": "Q17",
                "edition": "29 CFR, Title 29, July 1, 2014 "
                             "edition, section 1910.147",
                "edition_basis": "The edition is identified by the "
                                 "govinfo package identifier "
                                 "(CFR-2014-title29-vol5 = the "
                                 "annual edition of Title 29, volume "
                                 "5, revised as of July 1) and "
                                 "corroborated by the GPO typesetting "
                                 "footer on every page ('29 CFR Ch. "
                                 "XVII (7-1-14 Edition)').",
                "url": "https://www.govinfo.gov/content/pkg/"
                       "CFR-2014-title29-vol5/pdf/"
                       "CFR-2014-title29-vol5-sec1910-147.pdf",
                "retrieved_utc": "2026-10-03T09:44:54Z",
                "file": "sources/CFR-2014-title29-vol5-sec1910-147.pdf",
                "bytes": PDF_147_PATH.stat().st_size,
                "sha256": sha256_file(PDF_147_PATH),
                "text_extraction": "sources/"
                                   "CFR-2014-title29-vol5-sec1910-147.txt",
                "text_bytes": TEXT_147_PATH.stat().st_size,
                "text_sha256": sha256_file(TEXT_147_PATH),
                "text_extraction_tool": "pdftotext -layout "
                                        "(Poppler); the committed "
                                        ".txt is the hermetic test "
                                        "input",
            },
            {
                "what": "Stability cross-check: the tagout-device "
                        "attachment means' minimum unlocking strength "
                        "(no less than 50 pounds, "
                        "(c)(5)(ii)(C)(2)) and the energy-control "
                        "procedure's periodic inspection frequency "
                        "(at least annually, (c)(6)(i)) are identical "
                        "in the pinned July 1, 2014 annual edition "
                        "and in the current eCFR text as of 2026-10-01, "
                        "fetched via the eCFR versioner API - a "
                        "12-year span, which satisfies the command's "
                        "'unchanged for at least three years' "
                        "requirement for lookup sources.",
                "url": "https://www.ecfr.gov/api/versioner/v1/full/"
                       "2026-10-01/title-29.xml?part=1910"
                       "&section=1910.147",
                "retrieved_utc": "2026-10-03T09:47:12Z",
                "file": "sources/"
                        "ecfr-current-2026-10-01-sec1910-147.xml",
                "bytes": ECFR_147_PATH.stat().st_size,
                "sha256": sha256_file(ECFR_147_PATH),
            }
        ],
    }
    (HERE / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    if supplied == COMMAND_EXPECTED_COUNT:
        print(f"questions: {supplied} (command expects "
              f"{COMMAND_EXPECTED_COUNT} - count discrepancy "
              "resolved; FROZEN at " + DATASET_VERSION +
              " by the owner's signoff, "
              f"{freeze['signed_off_utc']})")
    else:
        print(f"questions: {supplied} (command expects "
              f"{COMMAND_EXPECTED_COUNT} - NOT frozen)")
    print(f"candidate sha256: {raw_hash}")
    for q in questions:
        print(f"  {q['id']} {q['shape']:<11} {q['domain']}")


if __name__ == "__main__":
    main()
