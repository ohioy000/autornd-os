"""The tier-2 candidate dataset is verified, separated and versioned
(ARCH-20261002-117).

The owner's tier-2 command requires, per question: deterministic
recomputation of every numerical key; checks of dimensions, boundary
operators, discrete selections and tolerances; verification that each
claimed wrong answer is actually wrong under the stated assumptions;
and, for lookup questions, verbatim quotation matches against archived
sources. `evals/tier2/verify_keys.py` performs those checks against
first principles; `evals/tier2/scorer.py` is the provider-free scorer
that scores free-text answers against the keys. This file runs both
instruments, proves each can fail on a corrupted copy (convention 22 -
an instrument written in the same commit as the dataset gets no run of
its own to prove it on), checks the three-way separation the command
requires, records the open item that blocks freezing (the supplied
array holds 5 of the 25 questions the command expects), and guards the
version record the way D44 guards the golden scoreboard.
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
TIER2 = ROOT / "evals" / "tier2"
MANIFEST = json.loads((TIER2 / "manifest.json").read_text(encoding="utf-8"))
QUESTIONS = json.loads(
    (TIER2 / "questions.json").read_text(encoding="utf-8"))
KEYS = json.loads((TIER2 / "keys.json").read_text(encoding="utf-8"))
QUESTION_IDS = [q["id"] for q in QUESTIONS]


def _verify(directory: Path) -> subprocess.CompletedProcess:
    """Run the verifier's own entry point against a directory.

    The instrument comes from the tree; only the data is pointed
    at the copy, so a corrupted copy tests the instrument, not a
    corrupted instrument.
    """
    return subprocess.run(
        [sys.executable, str(TIER2 / "verify_keys.py"),
         "--dir", str(directory)],
        capture_output=True, text=True)


def _self_test(directory: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(directory / "scorer.py"),
         "--self-test"],
        capture_output=True, text=True)


def _copy_tree(tmp_path: Path) -> Path:
    copy = tmp_path / "tier2"
    shutil.copytree(TIER2, copy)
    return copy


class TestTheVerifierHoldsTheKeys:
    """verify_keys.py recomputes every numerical key from first
    principles and checks the source claims against the archived
    regulation text. It must pass on the tree and prove it can
    fail on corrupted copies."""

    def test_every_check_holds_on_the_tree(self):
        out = _verify(TIER2)
        assert out.returncode == 0, out.stdout + out.stderr
        assert "VERIFICATION PASSED: all 61 checks hold" in out.stdout
        # Convention 28: the instrument examined all five questions
        # and reports the open item beside its result.
        for i in range(1, 6):
            assert f"Q{i}." in out.stdout, (
                f"the verifier's table holds no Q{i} check - it "
                f"examined fewer questions than the dataset has")
        assert "5 questions verified" in out.stdout
        assert "NOT frozen" in out.stdout
        assert "20 questions short" in out.stdout

    def test_a_corrupted_numeric_key_fails_the_cross_check(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        keys = json.loads((copy / "keys.json").read_text(
            encoding="utf-8"))
        q1 = next(k for k in keys if k["id"] == "Q1")
        q1["required_items"][0]["value"] = (
            "$+8.50\\,\\mathrm{V}$ relative to ground")
        (copy / "keys.json").write_text(
            json.dumps(keys, indent=2) + "\n", encoding="utf-8")
        out = _verify(copy)
        assert out.returncode == 1
        assert "VERIFICATION FAILED: 1/61 checks failed: X1" in (
            out.stdout)

    def test_a_corrupted_candidate_export_fails_the_hash(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        with (copy / MANIFEST["candidate"]["file"]).open("ab") as f:
            f.write(b"x")
        out = _verify(copy)
        assert out.returncode == 1
        assert "VERIFICATION FAILED: 1/61 checks failed: G1" in (
            out.stdout)

    def test_a_corrupted_source_archive_fails_the_archive_hash(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        archive = MANIFEST["source_archives"][0]["file"]
        with (copy / archive).open("ab") as f:
            f.write(b"x")
        out = _verify(copy)
        assert out.returncode == 1
        assert "VERIFICATION FAILED: 1/61 checks failed: Q2.1" in (
            out.stdout)

    def test_swapped_model_answer_steps_fail_the_order_check(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        keys = json.loads((copy / "keys.json").read_text(
            encoding="utf-8"))
        q5 = next(k for k in keys if k["id"] == "Q5")
        steps = q5["model_answer"].split("\n")
        steps[0], steps[1] = steps[1], steps[0]
        q5["model_answer"] = "\n".join(steps)
        (copy / "keys.json").write_text(
            json.dumps(keys, indent=2) + "\n", encoding="utf-8")
        out = _verify(copy)
        assert out.returncode == 1
        assert "VERIFICATION FAILED: 1/61 checks failed: Q5.5" in (
            out.stdout)


class TestTheScorerScoresNotRegexes:
    """scorer.py is the provider-free scorer: it scores free-text
    answers against the keys with unit conversion and tolerance
    comparison, not regex presence. Its self-test must pass on the
    tree, and a corrupted key must fail the intact model answer."""

    def test_the_self_test_passes(self):
        out = _self_test(TIER2)
        assert out.returncode == 0, out.stdout + out.stderr
        assert ("SCORER SELF-TEST PASSED: all 64 fixtures hold"
                in out.stdout)
        for qid in QUESTION_IDS:
            assert f"{qid} model answer" in out.stdout, (
                f"the self-test never ran {qid}'s model answer")
        # Convention 28: the scorer reports the open item beside
        # its result, not just a green count.
        assert "Candidate holds 5 questions" in out.stdout
        assert "NOT frozen" in out.stdout

    def test_a_corrupted_key_fails_the_intact_model_answer(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        keys = json.loads((copy / "keys.json").read_text(
            encoding="utf-8"))
        q1 = next(k for k in keys if k["id"] == "Q1")
        q1["required_items"][0]["value"] = (
            "$+8.50\\,\\mathrm{V}$ relative to ground")
        (copy / "keys.json").write_text(
            json.dumps(keys, indent=2) + "\n", encoding="utf-8")
        # The scorer reads its keys from its own directory at
        # import time, so the copy is imported as the module.
        sys.path.insert(0, str(copy))
        try:
            sys.modules.pop("scorer", None)
            import scorer
            intact = next(k for k in KEYS if k["id"] == "Q1")
            result = scorer.score("Q1", intact["model_answer"])
        finally:
            sys.path.remove(str(copy))
            sys.modules.pop("scorer", None)
        assert result["verdict"] == "FAIL"
        failed = [i["item"] for i in result["items"]
                  if not i["pass"]]
        assert "Output voltage" in failed


class TestTheDatasetIsVersioned:
    """The tier-2 set is versioned the way D44 versions the golden
    scoreboard: the manifest names the current versions.json entry,
    and the four versioned files hash to it. A change to any of the
    four is a new version - an entry naming the change and what
    triggered it."""

    @staticmethod
    def _assert_versioned(directory: Path) -> None:
        manifest = json.loads(
            (directory / "manifest.json").read_text(encoding="utf-8"))
        versions = json.loads(
            (directory / "versions.json").read_text(encoding="utf-8"))
        named = manifest["dataset_version"]
        assert manifest["scorer_version"] == named, (
            f"manifest.json names dataset version {named} but "
            f"scorer version {manifest['scorer_version']} - the "
            f"two must name the same entry")
        assert versions["versions"], (
            f"Ruling D44 (applied to the tier-2 set): "
            f"versions.json has no entries at all, so manifest "
            f"version {named} has no entry. A key change is a new "
            f"version: an entry naming the change and what "
            f"triggered it.")
        entry = next(
            (e for e in versions["versions"]
             if e["version"] == named), None)
        assert entry is not None, (
            f"Ruling D44 (applied to the tier-2 set): manifest "
            f"names version {named} and versions.json has no entry "
            f"for it. A key change is a new version: an entry "
            f"naming the change and what triggered it.")
        assert versions["versions"][-1]["version"] == named, (
            f"manifest.json names {named} but versions.json's "
            f"current entry is "
            f"{versions['versions'][-1]['version']} - the manifest "
            f"must name the current entry")
        for name in ("questions.json", "keys.json", "scorer.py",
                     "verify_keys.py"):
            actual = hashlib.sha256(
                (directory / name).read_bytes()).hexdigest()
            assert actual == entry["sha256"][name], (
                f"Ruling D44 (applied to the tier-2 set): {name} "
                f"no longer hashes to the version {named} entry in "
                f"versions.json (recorded "
                f"{entry['sha256'][name]}, found {actual}). A "
                f"defect a reading finds in a key is fixed only as "
                f"a new version, after the run that found it has "
                f"been reported under the old one.")

    def test_the_tree_matches_the_recorded_version(self):
        self._assert_versioned(TIER2)

    def test_a_one_byte_change_in_a_copy_fails_naming_the_rule(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        text = (copy / "keys.json").read_text(encoding="utf-8")
        # One digit, deep in the first record, so the drift is in
        # key content and the copy stays parseable JSON.
        start = text.index('"required_items"')
        i = next(j for j in range(start, len(text))
                 if text[j].isdigit())
        (copy / "keys.json").write_text(
            text[:i] + str((int(text[i]) + 1) % 10) + text[i + 1:],
            encoding="utf-8")
        with pytest.raises(AssertionError) as exc:
            self._assert_versioned(copy)
        assert "no longer hashes" in str(exc.value)
        assert "new version" in str(exc.value)

    def test_a_missing_versions_entry_fails_naming_the_rule(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        versions = json.loads(
            (copy / "versions.json").read_text(encoding="utf-8"))
        versions["versions"] = [
            e for e in versions["versions"]
            if e["version"] != MANIFEST["dataset_version"]]
        (copy / "versions.json").write_text(
            json.dumps(versions), encoding="utf-8")
        with pytest.raises(AssertionError) as exc:
            self._assert_versioned(copy)
        assert "no entry" in str(exc.value)
        assert "new version" in str(exc.value)

    def test_an_empty_versions_list_fails_naming_the_rule(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        versions = json.loads(
            (copy / "versions.json").read_text(encoding="utf-8"))
        versions["versions"] = []
        (copy / "versions.json").write_text(
            json.dumps(versions), encoding="utf-8")
        with pytest.raises(AssertionError) as exc:
            self._assert_versioned(copy)
        assert "no entries" in str(exc.value)
        assert "new version" in str(exc.value)


class TestTheDatasetSeparation:
    """The command requires the dataset to separate (1) model-visible
    requests, (2) reference source documents, and (3) scorer-only
    keys, worked answers and wrong-answer examples. The model-visible
    file carries exactly the request; no key value may leak into it;
    the scorer-only file carries no request text."""

    def test_model_visible_requests_carry_no_scorer_material(self):
        for q in QUESTIONS:
            assert set(q) == {"id", "shape", "domain", "question"}, (
                f"{q['id']} carries more than the model-visible "
                f"request: {sorted(set(q))}")

    def test_no_key_values_leak_into_the_model_visible_file(self):
        text = (TIER2 / "questions.json").read_text(encoding="utf-8")
        # Numerical keys and the lookup thresholds. Stated inputs
        # (6.00 kN, 10.0 bar, 300 s) belong to the questions; the
        # answers do not.
        for probe in ("19.5", "23.5", "19.5 percent",
                      "23.5 percent", "6.13592", "20.3718",
                      "0.0101859", "0.2355", "8.00", "8.0",
                      "8000", "0.10"):
            assert probe not in text, (
                f"the model-visible file carries the key value "
                f"{probe!r} - scorer material leaked into what "
                f"every arm's model sees")

    def test_the_scorer_only_file_carries_no_model_visible_request(
            self):
        for k in KEYS:
            assert "question" not in k, (
                f"{k['id']} carries the question text in the "
                f"scorer-only file")


class TestTheManifestRecordsTheOpenItem:
    """The supplied array holds 5 of the 25 questions the command
    expects. That discrepancy is the freeze blocker: it is recorded,
    not resolved, because resolving it means supplying questions,
    which the command forbids the executor (and any AI model) to
    do. The source archives the verification depends on must match
    the files on disk."""

    def test_the_count_discrepancy_is_recorded_not_resolved(self):
        assert MANIFEST["questions"] == 5
        assert MANIFEST["command_expected_questions"] == 25
        assert MANIFEST["frozen"] is False
        blockers = MANIFEST["freeze_blocked_by"]
        assert blockers, "no freeze blocker recorded"
        assert any("count-discrepancy" in b for b in blockers), (
            "the recorded freeze blockers do not name the count "
            "discrepancy")

    def test_the_source_archives_match_the_files_on_disk(self):
        archives = MANIFEST["source_archives"]
        assert len(archives) == 2, (
            "the manifest records a different number of source "
            "archives than the verification reads")
        first = archives[0]
        for field, path_key in (("file", "file"),
                                ("text_extraction",
                                 "text_extraction")):
            path = TIER2 / first[path_key]
            assert path.exists(), f"missing archive {path}"
            assert path.stat().st_size == first[
                "bytes" if path_key == "file" else "text_bytes"]
            recorded = first["sha256" if path_key == "file"
                             else "text_sha256"]
            actual = hashlib.sha256(
                path.read_bytes()).hexdigest()
            assert actual == recorded, (
                f"{path.name} hashes to {actual}, the manifest "
                f"records {recorded}")
        crosscheck = archives[1]
        path = TIER2 / crosscheck["file"]
        assert path.exists(), f"missing archive {path}"
        assert path.stat().st_size == crosscheck["bytes"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == crosscheck["sha256"]


class TestTheExtractionIsIdempotent:
    """extract_candidate.py derives the separated forms from the raw
    export. Re-running it on a copy of the tree must change nothing:
    the dataset is the export, and the derived files are functions
    of it."""

    def test_rerunning_the_extraction_changes_nothing(self, tmp_path):
        copy = _copy_tree(tmp_path)
        out = subprocess.run(
            [sys.executable, str(copy / "extract_candidate.py")],
            capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr
        for name in ("questions.json", "keys.json", "manifest.json"):
            assert (copy / name).read_bytes() == (
                TIER2 / name).read_bytes(), (
                f"re-running the extraction rewrote {name}")
