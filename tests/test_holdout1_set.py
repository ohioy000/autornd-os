"""The first hold-out set, version 1.1: the set as the owner signed it on 2026-11-17 with X41 removed on the owner's
instruction of 2026-11-25 (D44: a change to a signed set is a new version the owner ratifies).

X41's key names the ATmega328P datasheet PDF, which states no thermal figure (all 310,048 characters read on 2026-11-25),
while Microchip's online documentation for the same part prints one (theta-JA 60 degC/W, 28-pin PDIP); answers that quoted that
real page were scored against a key that says there is none. The signed set is kept byte for byte beside the live one so every
earlier reading of 42 questions can still be reproduced.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "evals" / "professional" / "holdout-questions.json"
SIGNED = ROOT / "evals" / "professional" / "holdout-questions-v1.json"
RUNNER = ROOT / "docs" / "probes" / "short_workflows_measurement.py"

# The file as signed on 2026-11-17 (42 questions), and version 1.1 of 2026-11-25 (41). A further change is a new version
# the owner ratifies, with a new hash here, in the same change, on purpose.
SIGNED_SHA256 = "c5d4a9dad66ee6452511026ca2674eb032a6e9176eaf9a88ec38e716fd52eee1"
LIVE_SHA256 = "f5821e6045ee7f578415bfb5062095c218cfb8d9c783efc5f5f48769096c81d6"


@pytest.fixture(scope="module")
def live() -> dict:
    return json.loads(LIVE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def signed() -> dict:
    return json.loads(SIGNED.read_text(encoding="utf-8"))


class TestTheSignedSetIsKept:
    def test_the_archive_is_byte_for_byte_the_set_the_owner_signed(self):
        assert hashlib.sha256(SIGNED.read_bytes()).hexdigest() == SIGNED_SHA256

    def test_the_archive_holds_all_42_questions_with_x41(self, signed):
        assert signed["version"] == "professional-holdout-1"
        assert len(signed["questions"]) == 42
        assert "X41" in {q["id"] for q in signed["questions"]}


class TestVersionOnePointOne:
    def test_the_file_is_byte_for_byte_the_ratified_one(self):
        assert hashlib.sha256(LIVE.read_bytes()).hexdigest() == LIVE_SHA256, \
            "a change to a signed set is a new version the owner ratifies (D44), with a new hash here"

    def test_x41_is_gone_and_41_questions_remain(self, live):
        ids = {q["id"] for q in live["questions"]}
        assert "X41" not in ids and len(live["questions"]) == 41

    def test_nothing_else_changed_every_other_question_is_identical_to_the_signed_one(self, live, signed):
        kept = [q for q in signed["questions"] if q["id"] != "X41"]
        assert live["questions"] == kept

    def test_the_version_names_itself_and_says_what_was_removed(self, live):
        assert live["version"] == "professional-holdout-1.1"
        assert live["changes"][0]["removed"] == ["X41"] and live["changes"][0]["previous"].endswith("-v1.json")
        assert not str(live["status"]).upper().startswith("DRAFT")
        assert "owner" in live["status"]

    def test_the_runner_reads_the_live_file_for_the_professional_holdout(self):
        text = RUNNER.read_text(encoding="utf-8")
        assert re.search(r'"professional-holdout":\s*"holdout-questions.json"', text)
