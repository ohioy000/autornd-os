"""The golden set's keys are a guard (ARCH-20261001-102, D41's measurement
exception).

evals/golden/score.py is advisor-written ground truth: every model answer
holds every item, every listed wrong answer is caught, every alternative
phrasing holds, and the IA model answer holds its core items. This file runs
that self-test, and proves it can fail by corrupting one pattern in a copy of
keys.json. It also drives score_trace.py over a written record, because the
scorer that reads a trace is the executor's and gets no other run to prove
it on (convention 22).

Ruling D44 (ARCH-20261002-108): the scoreboard is frozen and versioned.
keys.json and score.py must hash to the entry evals/golden/versions.json keeps
for the version keys.json names; a score names its key version.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "evals" / "golden"
KEYS = json.loads((GOLDEN / "keys.json").read_text(encoding="utf-8"))


def _self_test(directory: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(directory / "score.py")],
                          capture_output=True, text=True)


class TestTheKeysHoldTheirOwnAnswers:
    def test_the_advisor_self_test_passes(self):
        out = _self_test(GOLDEN)
        assert out.returncode == 0, out.stdout + out.stderr
        assert "SELF-TEST PASSED" in out.stdout
        # Convention 28: it examined all six questions and the side test.
        assert all(f"Q{i} model answer: ALL HOLD" in out.stdout for i in range(1, 7))
        assert "IA model answer core:" in out.stdout

    def test_a_corrupted_pattern_fails_it(self, tmp_path):
        shutil.copy(GOLDEN / "score.py", tmp_path / "score.py")
        broken = json.loads(json.dumps(KEYS))
        broken["golden"][0]["items"][0]["all"] = ["\\b9(?:\\.0+)?\\s*v\\b"]
        (tmp_path / "keys.json").write_text(json.dumps(broken), encoding="utf-8")
        out = _self_test(tmp_path)
        assert out.returncode == 1
        assert "Q1 model answer: FAILS ['Q1.1']" in out.stdout
        assert "SELF-TEST FAILED" in out.stdout


class TestTheTraceScorerReadsTheWrittenRecord:
    @staticmethod
    def _trace(tmp_path, units) -> Path:
        path = tmp_path / "results.jsonl"
        lines = [{"record": "header", "max_spend": 0.07}] + units
        path.write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")
        return path

    def _rows(self, tmp_path, units):
        sys.path.insert(0, str(GOLDEN))
        try:
            import score_trace
        finally:
            sys.path.remove(str(GOLDEN))
        return score_trace.main(str(self._trace(tmp_path, units)))

    def test_a_shipped_model_answer_passes_and_a_blocked_run_without_one_fails(self, tmp_path):
        q1 = KEYS["golden"][0]
        units = [
            {"record": "unit", "scenario": "golden_q1", "status": "completed",
             "seconds": 120.0, "cost": 0.02,
             "verdicts": {"implement": {"summary": q1["model_answer"]},
                          "triage": {"risk": "low"}}},
            {"record": "unit", "scenario": "golden_q3", "status": "blocked",
             "seconds": 299.0, "cost": 0.05, "verdicts": {},
             "watchdog": {"approved": {"index": None}}, "iterations": []},
        ]
        q1_row, q3_row = self._rows(tmp_path, units)
        assert q1_row["verdict"] == "PASS" and q1_row["sprawl"] == 1.0
        assert q3_row["verdict"] == "FAIL (no answer)"

    def test_an_approved_unshipped_answer_is_scored_but_never_passes(self, tmp_path):
        q6 = KEYS["golden"][5]
        units = [{"record": "unit", "scenario": "golden_q6", "status": "blocked",
                  "seconds": 100.0, "cost": 0.03, "verdicts": {},
                  "watchdog": {"approved": {"index": 0}},
                  "iterations": [{"implement_summary": q6["model_answer"]}]}]
        (row,) = self._rows(tmp_path, units)
        assert row["answer"] == "approved, not shipped"
        assert all(row["items"].values())
        assert row["verdict"] == "FAIL"

    def test_a_late_shipped_answer_fails_on_time(self, tmp_path):
        q2 = KEYS["golden"][1]
        units = [{"record": "unit", "scenario": "golden_q2", "status": "completed",
                  "seconds": 301.0, "cost": 0.02,
                  "verdicts": {"implement": {"summary": q2["model_answer"]}}}]
        (row,) = self._rows(tmp_path, units)
        assert all(row["items"].values()) and row["within_target"] is False
        assert row["verdict"] == "FAIL"


class TestTheScoreboardIsFrozenAndVersioned:
    """Ruling D44: keys.json and score.py hash to the entry versions.json keeps
    for the version keys.json names. A missing entry and a hash mismatch both
    fail, each naming D44."""

    @staticmethod
    def _assert_frozen(directory: Path) -> None:
        keys = json.loads((directory / "keys.json").read_text(encoding="utf-8"))
        versions = json.loads((directory / "versions.json").read_text(encoding="utf-8"))
        entry = next((e for e in versions["versions"]
                      if e["version"] == keys["version"]), None)
        assert entry is not None, (
            f"Ruling D44: keys.json names key version {keys['version']} and "
            f"versions.json has no entry for it. A key change is a new version: "
            f"an entry naming the change and what triggered it.")
        for name in ("keys.json", "score.py"):
            actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
            assert actual == entry["sha256"][name], (
                f"Ruling D44: {name} no longer hashes to the key version "
                f"{keys['version']} entry in versions.json (recorded "
                f"{entry['sha256'][name]}, found {actual}). A defect a reading "
                f"finds in a key is fixed only as a new version, after the run "
                f"that found it has been reported under the old one.")

    def test_the_tree_matches_the_recorded_version(self):
        self._assert_frozen(GOLDEN)

    def test_a_one_byte_change_in_a_copy_fails_naming_d44(self, tmp_path):
        for name in ("keys.json", "score.py", "versions.json"):
            shutil.copy(GOLDEN / name, tmp_path / name)
        text = (tmp_path / "keys.json").read_text(encoding="utf-8")
        # One digit, past the "version" field, so the drift is in key content
        # and the copy stays parseable JSON.
        start = text.index('"golden"')
        i = next(j for j in range(start, len(text)) if text[j].isdigit())
        (tmp_path / "keys.json").write_text(
            text[:i] + str((int(text[i]) + 1) % 10) + text[i + 1:], encoding="utf-8")
        with pytest.raises(AssertionError) as exc:
            self._assert_frozen(tmp_path)
        assert "Ruling D44" in str(exc.value)
        assert "no longer hashes" in str(exc.value)

    def test_a_missing_versions_entry_fails_naming_d44(self, tmp_path):
        for name in ("keys.json", "score.py", "versions.json"):
            shutil.copy(GOLDEN / name, tmp_path / name)
        versions = json.loads((tmp_path / "versions.json").read_text(encoding="utf-8"))
        versions["versions"] = [e for e in versions["versions"]
                                if e["version"] != KEYS["version"]]
        (tmp_path / "versions.json").write_text(json.dumps(versions), encoding="utf-8")
        with pytest.raises(AssertionError) as exc:
            self._assert_frozen(tmp_path)
        assert "Ruling D44" in str(exc.value)
        assert "no entry" in str(exc.value)


class TestEveryScoreNamesItsKeyVersion:
    """D44: every report states the key version beside each score — the
    trace scorer's summary line and the baseline's report and trace header."""

    def test_the_trace_summary_names_the_key_version(self, tmp_path, capsys):
        q1 = KEYS["golden"][0]
        units = [{"record": "unit", "scenario": "golden_q1", "status": "completed",
                  "seconds": 120.0, "cost": 0.02,
                  "verdicts": {"implement": {"summary": q1["model_answer"]}}}]
        sys.path.insert(0, str(GOLDEN))
        try:
            import score_trace
        finally:
            sys.path.remove(str(GOLDEN))
        score_trace.main(str(TestTheTraceScorerReadsTheWrittenRecord._trace(
            tmp_path, units)))
        summary = capsys.readouterr().out.splitlines()[-1]
        assert f"key v{KEYS['version']}" in summary
