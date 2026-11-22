"""The second hold-out set is in the repo as a draft, and no paid answer is made on a draft.

The 182 questions (Y1 to Y182, thirteen groups of 14) were written and checked by models through
evals/professional/write_holdout.py; 181 passed the code check and two readings, and every passage
and figure of those 181 was found on its live page by evals/professional/verify_keys.py on 2026-11-21
('181 of 181 hold'). Y48 was held back for a nit in its key. The owner signs the keys (D44); until
then the runner refuses the set, and these tests pin that, so a draft cannot be run by accident and
a signed set is a deliberate edit of its status.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SET_FILE = ROOT / "evals" / "professional" / "holdout2-questions.json"
RUNNER = ROOT / "docs" / "probes" / "short_workflows_measurement.py"


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(SET_FILE.read_text(encoding="utf-8"))


class TestTheDraftIsWhatTheScriptMade:
    def test_it_is_named_and_marked_a_draft(self, data):
        assert data["version"] == "professional-holdout-2"
        assert str(data["status"]).upper().startswith("DRAFT"), \
            "the runner refuses a set whose status starts with DRAFT; signing is the owner's edit"

    def test_it_holds_181_of_the_182_ids_and_not_y48(self, data):
        ids = [q["id"] for q in data["questions"]]
        assert len(ids) == len(set(ids)) == 181
        assert set(ids) <= {f"Y{n}" for n in range(1, 183)}
        assert set(f"Y{n}" for n in range(1, 183)) - set(ids) == {"Y48"}

    def test_every_question_has_its_sources_and_its_key(self, data):
        for q in data["questions"]:
            assert q["question"].strip() and q["field"].strip(), q["id"]
            assert q["sources"] and all(s["url"].startswith("http") and s["passage"].strip()
                                        for s in q["sources"]), q["id"]
            assert q["key"] and all(k["item"].strip() and str(k["answer"]).strip()
                                    for k in q["key"]), q["id"]


class TestTheRunnerRefusesADraft:
    def test_the_set_is_registered_by_name(self):
        text = RUNNER.read_text(encoding="utf-8")
        assert re.search(r'"professional-holdout-2":\s*"holdout2-questions.json"', text)

    def test_a_run_on_the_draft_is_refused_before_any_work(self, tmp_path):
        env = {**os.environ, "MEASURE_SET": "professional-holdout-2"}
        for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION", "RESEARCH", "SEARCH"):
            env[f"MODEL_{tier}"] = "placeholder/offline"
        env.pop("OPENROUTER_API_KEY", None)
        done = subprocess.run([sys.executable, str(RUNNER), str(tmp_path / "out.jsonl"),
                               "0", "1", "1", "0"], capture_output=True, text=True, timeout=120,
                              env=env, cwd=str(ROOT))
        assert done.returncode != 0
        assert "is a draft: its keys are not signed off" in done.stderr
        out = tmp_path / "out.jsonl"        # the runner makes it a directory of results
        written = [f for f in out.rglob("*") if f.is_file() and f.stat().st_size] if out.exists() else []
        assert written == [], "no record was written, so nothing was spent"
