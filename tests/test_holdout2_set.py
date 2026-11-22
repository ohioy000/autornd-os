"""The second hold-out set is signed by the owner and frozen, and it is the set that was checked.

The 182 questions (Y1 to Y182, thirteen groups of 14) were written and checked by models through
evals/professional/write_holdout.py; 181 passed the code check and two readings. verify_keys.py found
every passage and figure of the 181 on the live pages on 2026-11-21 ('181 of 181 hold'). Haiku read all
181 once on 2026-11-21 and 2026-11-22; of its 47 FIX verdicts, seven were real defects and the owner
had those dropped (Y10, Y55, Y87, Y93, Y96, Y97, Y107), and Y48 had been held back by the script, so the
set holds 174. The owner signed the keys on 2026-11-22 (D44). These tests pin that: the set is exactly
what was signed (a byte-for-byte hash), a change is a new version the owner ratifies, and the runner
accepts a signed set and still refuses a draft.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SET_FILE = ROOT / "evals" / "professional" / "holdout2-questions.json"
RUNNER = ROOT / "docs" / "probes" / "short_workflows_measurement.py"

# The file as the owner signed it on 2026-11-22. Editing the set means a new version the owner ratifies
# (D44) and a new hash here, in the same change, on purpose.
SIGNED_SHA256 = "949b7d241ab3e48141ef5d62c44f3f4a5e1e0c2755a824cf355b3bb053f9ecad"
WITHHELD = {"Y10", "Y48", "Y55", "Y87", "Y93", "Y96", "Y97", "Y107"}


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(SET_FILE.read_text(encoding="utf-8"))


class TestTheSetIsWhatTheOwnerSigned:
    def test_the_file_is_byte_for_byte_the_signed_one(self):
        assert hashlib.sha256(SET_FILE.read_bytes()).hexdigest() == SIGNED_SHA256, \
            "a change to a signed set is a new version the owner ratifies (D44), with a new hash here"

    def test_it_is_named_and_marked_approved(self, data):
        assert data["version"] == "professional-holdout-2"
        assert str(data["status"]).startswith("Approved by the owner on 2026-11-22")
        assert not str(data["status"]).upper().startswith("DRAFT")

    def test_it_holds_the_182_ids_less_the_eight_withheld_ones(self, data):
        ids = [q["id"] for q in data["questions"]]
        assert len(ids) == len(set(ids)) == 174
        assert {f"Y{n}" for n in range(1, 183)} - set(ids) == WITHHELD

    def test_each_withheld_id_says_why_and_none_of_them_is_in_the_set(self, data):
        assert set(data["withheld"]) == WITHHELD
        assert all(len(reason) > 20 for reason in data["withheld"].values())
        assert WITHHELD.isdisjoint(q["id"] for q in data["questions"])

    def test_every_question_has_its_sources_and_its_key(self, data):
        for q in data["questions"]:
            assert q["question"].strip() and q["field"].strip(), q["id"]
            assert q["sources"] and all(s["url"].startswith("http") and s["passage"].strip()
                                        for s in q["sources"]), q["id"]
            assert q["key"] and all(k["item"].strip() and str(k["answer"]).strip()
                                    for k in q["key"]), q["id"]


class TestTheRunnerAcceptsASignedSetAndRefusesADraft:
    def test_the_set_is_registered_by_name(self):
        text = RUNNER.read_text(encoding="utf-8")
        assert re.search(r'"professional-holdout-2":\s*"holdout2-questions.json"', text)

    def test_the_runner_still_refuses_a_status_that_says_draft(self):
        text = RUNNER.read_text(encoding="utf-8")
        assert 'str(frozen.get("status", "")).upper().startswith("DRAFT")' in text
        assert "is a draft: its keys are not signed off" in text
