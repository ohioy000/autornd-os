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
requires, records the freeze the owner's signoff ratified, and
guards the version record the way D44 guards the golden scoreboard.
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
        assert "VERIFICATION PASSED: all 268 checks hold" in out.stdout
        # Convention 28: the instrument examined all 25
        # questions and reports the open item beside its
        # result.
        for i in range(1, 26):
            assert f"Q{i}." in out.stdout, (
                f"the verifier's table holds no Q{i} check - it "
                f"examined fewer questions than the dataset has")
        assert "25 questions verified" in out.stdout
        # The instrument reports the freeze beside its
        # result: the set is frozen by the owner's
        # signoff, not merely counted.
        assert "frozen at frozen-2026-10-03" in out.stdout
        assert "signoff" in out.stdout

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
        assert "VERIFICATION FAILED: 1/268 checks failed: X1" in (
            out.stdout)

    def test_a_corrupted_candidate_export_fails_the_hash(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        with (copy / MANIFEST["candidate"]["file"]).open("ab") as f:
            f.write(b"x")
        out = _verify(copy)
        assert out.returncode == 1
        assert "VERIFICATION FAILED: 1/268 checks failed: G1" in (
            out.stdout)

    def test_a_corrupted_source_archive_fails_the_archive_hash(
            self, tmp_path):
        copy = _copy_tree(tmp_path)
        archive = MANIFEST["source_archives"][0]["file"]
        with (copy / archive).open("ab") as f:
            f.write(b"x")
        out = _verify(copy)
        assert out.returncode == 1
        assert "VERIFICATION FAILED: 1/268 checks failed: Q2.1" in (
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
        assert "VERIFICATION FAILED: 1/268 checks failed: Q5.5" in (
            out.stdout)


class TestTheScorerScoresNotRegexes:
    """scorer.py is the provider-free scorer: it scores free-text
    answers against the keys with unit conversion and tolerance
    comparison, not regex presence. Its self-test must pass on the
    tree, and a corrupted key must fail the intact model answer."""

    def test_the_self_test_passes(self):
        out = _self_test(TIER2)
        assert out.returncode == 0, out.stdout + out.stderr
        assert ("SCORER SELF-TEST PASSED: all 248 fixtures hold"
                in out.stdout)
        for qid in QUESTION_IDS:
            assert f"{qid} model answer" in out.stdout, (
                f"the self-test never ran {qid}'s model answer")
        # Convention 28: the scorer reports the freeze
        # beside its result, not just a green count.
        assert "Candidate holds 25 questions" in out.stdout
        assert "frozen at frozen-2026-10-03" in out.stdout

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
                      "0.0101859", "0.2355", "8000",
                      # Q6-Q25: the derived keys, the accepted
                      # notations and the verdicts. Stated inputs
                      # that a question itself carries (8.00
                      # and 12.0 N/mm, 0.100 m, 35.0 deg C,
                      # 240 mm, 500 rpm, 3.04 V ...)
                      # are deliberately absent from this list.
                      "0,1,1,0", "8 h", "4 h", "2 h",
                      "133.333", "26.6667", "0.720", "15.0",
                      "PASS", "without restart",
                      "counterclockwise", "300 rpm",
                      "as nitrogen",
                      "8.64665", "0.135335",
                      "120000", "160 s",
                      "-0.030", "+0.010",
                      "0.480", "0.800480",
                      "50 lb", "annually",
                      "7.20", "20.8333", "1.15741",
                      "0.132", "0.264", "20.0 mA",
                      "2.04", "308.15",
                      "6 months", "14 h", "30 days",
                      "0.882353", "61.7647", "176.471",
                      "6.28319", "3:1", "12.0 N m",
                      "1.08", "1080"):
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


class TestTheManifestRecordsTheFreeze:
    """The owner supplied all 25 questions the command
    expects, so the count discrepancy the earlier state
    recorded is resolved, and the owner ratified the
    tier-2 signoff on 2026-10-03: the set is frozen.
    The manifest records the signoff - its grantor,
    time, scope and effect - and carries no freeze
    blocker. The source archives the verification
    depends on must match the files on disk."""

    def test_the_freeze_is_recorded_with_the_signoff(self):
        assert MANIFEST["questions"] == 25
        assert MANIFEST["command_expected_questions"] == 25
        assert MANIFEST["frozen"] is True, (
            "the owner ratified the tier-2 signoff on "
            "2026-10-03, but the manifest still records "
            "the set as unfrozen")
        assert MANIFEST["freeze_blocked_by"] == [], (
            "the manifest records freeze blockers after "
            "the owner's signoff cleared the last one")
        freeze = MANIFEST["freeze"]
        assert freeze["signed_off_by"] == "owner"
        assert freeze["signed_off_utc"] == "2026-10-03T21:41:20Z"
        assert "ratify the tier-2 signoff" in freeze["granted"]
        assert "verification" in freeze["scope"]
        assert "source review" in freeze["scope"]
        assert MANIFEST["dataset_version"] == "frozen-2026-10-03"
        assert MANIFEST["scorer_version"] == "frozen-2026-10-03"

    def test_the_source_archives_match_the_files_on_disk(self):
        archives = MANIFEST["source_archives"]
        assert len(archives) == 8, (
            "the manifest records a different number of "
            "source archives than the verification reads")
        for archive in archives:
            # Every archive records the archived document
            # itself; the govinfo PDFs additionally record
            # their text extraction (the eCFR snapshots are
            # already text).
            path = TIER2 / archive["file"]
            assert path.exists(), f"missing archive {path}"
            assert path.stat().st_size == archive["bytes"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == archive["sha256"], (
                f"{path.name} hashes to {actual}, the "
                f"manifest records {archive['sha256']}")
            if "text_extraction" in archive:
                text = TIER2 / archive["text_extraction"]
                assert text.exists(), f"missing archive {text}"
                assert text.stat().st_size == archive[
                    "text_bytes"]
                actual = hashlib.sha256(
                    text.read_bytes()).hexdigest()
                assert actual == archive["text_sha256"], (
                    f"{text.name} hashes to {actual}, the "
                    f"manifest records "
                    f"{archive['text_sha256']}")


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
