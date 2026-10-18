"""The tier-4 runner's tests (command ARCH-20261017-122's
acceptance criteria, R7/R8/R9 included).

Every test runs the real runner (evals/tier4/runner.py, imported
by path the way the tier-3 tests import it) against the frozen
batches (evals/tier4/pilot/ and evals/tier4/batch2/, read-only).
The mocked dry run is the instrument's own: scripted clients that
bill through the real guard and accounting, a fixture catalogue,
and a stand-in at the pipeline boundary for arms E and F. Nothing
reaches the network: the suite's guard (tests/conftest.py) refuses
every non-loopback socket, so the dry run's "no network" is proved
by the guard itself, not asserted here.

The runner reads every registered figure from the batch's own
manifest.json (R9): a frozen batch is data, and the tests read
the batches the way the runner does — through ``load_batch``.
Each test is proved by breaking one line of the runner and
quoting the failure - the break-proof is recorded under the test
it proves. A test that cannot fail proves nothing (convention 22).

The criteria, as the command orders them:
(a) the leakage guard - every unit of both modes carries only the
    given texts, with its break-proof;
(b) profile isolation - an F2 unit of F/E grounds with its own
    question's pages and no other question's, an F1 unit with
    none, with its break-proof;
(c) the freeze guard - a one-byte change to a batch's candidates,
    a corpus page or a docs/tier4 copy refuses, naming the file;
(d) the plan - the pilot calibration's nine units, batch 2's two,
    the pilot's refusals;
(e) the gate and the preflight - R4's exact-equality gate both
    ways, the credit preflight, the printed worst cases, the
    printed pins, the unpinned-arm refusal (R7), the 32768-token
    worst cases within the ceilings (R8);
(f) the mocked dry run of both modes of both batches - zero spend,
    every record field, the arm-blind reading sheet, every failure
    class, the void calibration's two defect classes recorded
    (R7, R8), the wiring proof (every single call carries its
    pin's provider order and the registered max_tokens);
(g) tier 3 unchanged - the scenario dispatch that the tier-4
    scenario ids generalize still keys the tier-3 dry run's own
    ids to the same workflows;
(h) the provider pins (R7) - the mapping, the empty-entry rule,
    the idempotency, the install-and-restore context, and the
    serving-mismatch comparison (on the provider's name, not
    the string form each side writes it in), with its break-proof;
(i) the batch registration (R9) - every registered figure, the
    sha256 conventions, the missing-field refusal;
(j) the paid path's pin source (R7) - the ratified
    line read from the paid runners' own .env.tier3
    file, not the ambient line the routing layer
    reads from .env, with its break-proof.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import random
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
TIER4 = ROOT / "evals" / "tier4"

# The runner, imported by path (evals/ is not an installed
# package - the tier-3 tests do the same). The registration in
# sys.modules precedes exec_module, and an instance the tier-3
# tests already loaded is reused, so one process holds one
# tier-3 module.
_SPEC = importlib.util.spec_from_file_location(
    "tier4_runner", TIER4 / "runner.py")
runner = importlib.util.module_from_spec(_SPEC)
sys.modules["tier4_runner"] = runner
_SPEC.loader.exec_module(runner)

tier3 = sys.modules["tier3_runner"]

# The two frozen batches, loaded the way the runner loads them.
PILOT = runner.load_batch()
BATCH2 = runner.load_batch(runner.TIER4 / "batch2")

QUESTIONS = PILOT.questions()
PAGES = [content for _name, content
         in PILOT.corpus_pages("T4-06")]
PAGE_NAMES = [name for name, _content
              in PILOT.corpus_pages("T4-06")]

# The two modes' plans, as the runner builds them.
CALIBRATION = runner.calibration_plan(PILOT)
PILOT_PLAN, _PILOT_REFUSALS = runner.pilot_plan(
    ["T4-02", "T4-03", "T4-04", "T4-06"], PILOT)


def _dry_run() -> dict[str, Any]:
    """The mocked dry run of both modes of both batches,
    once per session."""
    cached = getattr(_dry_run, "_result", None)
    if cached is None:
        cached = asyncio.run(runner.tier4_dry_run())
        _dry_run._result = cached
    return cached


def _outcome(batch_name: str, mode: str) -> dict[str, Any]:
    """One batch's one mode's mocked run."""
    return _dry_run()["batches"][batch_name][mode]


def _sheet(batch_name: str, mode: str) -> dict[str, Any]:
    """One batch's one mode's reading sheet."""
    return _dry_run()["reading_sheets"][batch_name][mode]


def _rates(catalogue: list[dict[str, Any]]
           ) -> dict[str, tuple[float, float]]:
    """The catalogue's rates, keyed by serving id."""
    return {
        entry["id"]: (float(entry["pricing"]["prompt"]),
                      float(entry["pricing"]["completion"]))
        for entry in catalogue}


# ── (a) The leakage guard ──────────────────────────────

class TestALeakageGuard:
    """The model-visible text is the candidate's request only,
    plus, for arm D on F2, the question's own corpus pages.
    Never the requirements, the reference design, the worked
    solution, the wrong designs or the difficulty rationale."""

    def test_every_unit_of_both_modes_carries_only_the_given_texts(
            self):
        """All 28 units of both modes: the arm's message carries
        no forbidden string the given texts do not state.

        Break-proof: change `model_visible_message` to append
        `candidate['requirements']` to the request, and the
        assertion fails with the requirement statements as
        findings - recorded: appending the requirements to
        T4-02's message flags all six statements."""
        for mode in ("calibration", "pilot"):
            for question_id, arm in _every_unit(mode):
                candidate = QUESTIONS[question_id]
                message = runner.model_visible_message(
                    arm, candidate, PILOT)
                given = PAGES if arm == "D-pages" else ()
                findings = runner.leakage_findings(
                    message, candidate, given=given)
                assert not findings, (mode, question_id, arm,
                                       findings[:2])

    def test_the_d_pages_message_is_the_registered_composition(
            self):
        """Arm D's F2 user message is the request, the registered
        separator, and the question's own corpus pages verbatim
        and in name order, each preceded by its file name - and
        the unit record's message sha256 is that message's.

        Break-proof: change `PAGES_SEPARATOR` to a different
        string, and the composition assert fails; change the
        manifest's page order, and the name-order assert
        fails."""
        candidate = QUESTIONS["T4-06"]
        pages = PILOT.corpus_pages("T4-06")
        expected = candidate["request"] + runner.PAGES_SEPARATOR + (
            "\n\n".join(
                f"{name}\n\n{content}"
                for name, content in pages))
        message = runner.d_pages_message(candidate, PILOT)
        assert message == expected
        assert len(PAGE_NAMES) == 3
        assert PAGE_NAMES == sorted(PAGE_NAMES)
        # The record's field is the composed message's own sha256.
        record = [
            record for record in _outcome(
                "pilot", "calibration")["records"]
            if record["arm"] == "D-pages"][0]
        assert record["message_sha256"] == (
            runner.sha256_bytes(message.encode("utf-8")))

    def test_break_proof_appending_the_requirements_flags_them(
            self):
        """The break-proof the command orders: append the
        requirements to the message and the guard fails.

        Break-proof: change `forbidden_strings` to skip
        requirement statements, and this test fails with empty
        findings - recorded: every requirement statement of every
        question is flagged when appended to its request."""
        for candidate in QUESTIONS.values():
            requirements = "\n".join(
                f"{requirement['id']}: {requirement['statement']}"
                for requirement in candidate["requirements"])
            for arm in ("A", "D"):
                leaked = (runner.model_visible_message(
                              arm, candidate, PILOT)
                          + "\n\n" + requirements)
                findings = runner.leakage_findings(leaked, candidate)
                assert findings, (candidate["id"], arm)
                assert all(finding in leaked for finding in findings)

    def test_break_proof_every_forbidden_class_is_covered(
            self):
        """The reference design, the worked solution, the wrong
        designs and the difficulty rationale, appended to a
        message, are each flagged - including by their string
        forms (the reference designs' values are mostly figures).

        Break-proof: change `_string_leaves` to skip numbers, and
        the reference-design case fails with empty findings -
        recorded: T4-02's figures (27.65, 104.09, 97.16) are
        flagged when appended."""
        candidate = QUESTIONS["T4-02"]
        cases = (
            str(candidate["reference_design"]),
            candidate["worked_solution"],
            candidate["difficulty_rationale"],
            str(candidate["wrong_designs"][0]["values"]),
            str(candidate["wrong_designs"][0]["reason"]),
        )
        for text in cases:
            leaked = candidate["request"] + "\n\n" + text
            findings = runner.leakage_findings(leaked, candidate)
            assert findings, (text[:40], findings)
        # The D-pages message, given the corpus, still flags an
        # appended worked solution - the corpus does not carry it.
        f2 = QUESTIONS["T4-06"]
        leaked = (runner.d_pages_message(f2, PILOT) + "\n\n"
                  + f2["worked_solution"])
        assert runner.leakage_findings(leaked, f2, given=PAGES)


def _every_unit(mode: str) -> list[tuple[str, str]]:
    """Every (question id, arm) pair the mode's plan runs."""
    return [(unit[0], unit[2])
            for unit in (CALIBRATION if mode == "calibration"
                         else PILOT_PLAN)]


# ── (b) Profile isolation ──────────────────────────────

class TestBProfileIsolation:
    """F2 units of arms F and E ground on their own question's
    pages; F1 units of every arm ground on nothing, so no corpus
    text reaches an F1 question."""

    def test_an_f2_unit_of_f_and_e_grounds_with_all_three_pages(
            self):
        """The tier-4 profile's grounding context is the three
        corpus pages, exactly as load_docs_context loads them.

        Break-proof: change `profiles/tier4.yaml`'s name to
        another value, and the context loads nothing - the
        manifest's directory is the profile's name, lowercased."""
        context = runner.corpus_context()
        for name, content in PILOT.corpus_pages("T4-06"):
            assert content in context, name
            assert f"tier4/{name}" in context

    def test_an_f1_unit_grounds_with_none(self):
        """The default profile's grounding context is empty - the
        default manifest carries no global documents, so an F1
        unit's pipeline reads no corpus text.

        Break-proof: add a global document to docs/manifest.json,
        and the assert fails with the document's text in the
        context."""
        with runner._profile_selected(None):
            context = runner.load_docs_context([], [])
        assert context == "", context[:80]

    def test_break_proof_an_f1_question_under_the_tier4_profile(
            self):
        """The break-proof the command orders: run an F1 question
        under the tier-4 profile and the test fails - the profile
        is the isolation mechanism, and an F1 question under it
        grounds the corpus pages.

        Break-proof: change `question_profile` to return
        `TIER4_PROFILE` for every unit, and the F1 records of the
        dry run would carry profile 'tier4' - the dry run's
        profile test below fails."""
        with runner._profile_selected(
                runner.load_profile(runner.TIER4_PROFILE)):
            context = runner.load_docs_context([], [])
        assert PILOT.corpus_pages("T4-06")[0][1] in context

    def test_the_units_run_under_their_registered_profile(
            self):
        """`unit_profile` names the question's own grounding
        profile for an F2 unit of F or E and the default for
        every other unit - D-pages carries the pages in its
        message, so it runs the single-call treatment under the
        default.

        Break-proof: change `unit_profile`'s condition to
        `family == 'F2'` alone, and the D-pages assert fails."""
        assert runner.unit_profile("T4-06", "E", PILOT).name == (
            "Tier4")
        assert runner.unit_profile("T4-06", "F", PILOT).name == (
            "Tier4")
        assert runner.unit_profile("T4-06", "D-pages", PILOT) is None
        for arm in ("A", "D", "E", "F"):
            assert runner.unit_profile("T4-02", arm, PILOT) is None

    def test_the_dry_run_records_carry_the_profile_each_unit_ran_under(
            self):
        """Every record of both modes carries the profile its unit
        ran under: 'tier4' for the F2 units of F and E, 'default'
        for every other unit.

        Break-proof: change `run_tier4_unit` to drop the
        `_profile_selected` wrapper, and the records still carry
        the field but the F2 units would ground on the process
        default - the records' profile field is the unit's own
        registration, and this test fails only if the field lies;
        the grounding itself is the two tests above."""
        for batch_name in ("pilot", "batch2"):
            for mode in ("calibration", "pilot"):
                for record in _outcome(
                        batch_name, mode)["records"]:
                    if (record["family"] == "F2"
                            and record["arm"] in ("E", "F")):
                        # The pilot batch's F2 question's pages
                        # are the tier-4 profile's own; another
                        # batch's F2 questions ground through
                        # their per-question profiles (R9).
                        wanted = ("Tier4" if batch_name == "pilot"
                                  else f"Tier4 {batch_name} "
                                       f"{record['question_id']}")
                    else:
                        wanted = "default"
                    assert record["profile"] == wanted, (
                        batch_name, mode, record["question_id"],
                        record["arm"], record["profile"], wanted)

    def test_each_f2_question_grounds_on_its_own_pages(
            self, two_f2_batch):
        """A synthetic batch of two F2 questions, each with its
        own corpus page: an F2 unit of F or E grounds with its
        own question's page and no other question's (R9) - the
        per-question grounding profile lists the question's
        frozen pages and nothing else.

        Break-proof: make the scratch manifests list every F2
        question's pages (shared pages), and both exclusion
        asserts fail - each context would carry the other
        question's page."""
        contexts = {
            question_id: runner.question_grounding_context(
                question_id, two_f2_batch)
            for question_id in ("Q-1", "Q-2")}
        assert "Q-1's own corpus page" in contexts["Q-1"]
        assert "Q-2's own corpus page" not in contexts["Q-1"]
        assert "Q-2's own corpus page" in contexts["Q-2"]
        assert "Q-1's own corpus page" not in contexts["Q-2"]
        # The question runs under its own profile, not the
        # shipped tier-4 profile the pilot batch's F2 question
        # runs under - its pages are not the tier-4 profile's.
        profile = runner.question_profile("Q-1", two_f2_batch)
        assert profile is not None
        assert profile.name == "Tier4 two-f2 Q-1"
        assert profile is not runner.load_profile(
            runner.TIER4_PROFILE)
        # D-pages carries its own question's page in its
        # message - the composition is the batch's own.
        candidate = two_f2_batch.questions()["Q-1"]
        message = runner.d_pages_message(candidate, two_f2_batch)
        assert "Q-1's own corpus page" in message
        assert "Q-2's own corpus page" not in message


@pytest.fixture
def two_f2_batch(tmp_path):
    """A synthetic frozen batch of two F2 questions, each with
    its own single corpus page, registered in the manifest's
    own format (R9) - the per-question grounding's test batch."""
    return runner.load_batch(_write_synthetic_batch(
        tmp_path / "two-f2", "two-f2",
        {"Q-1": "Q-1's own corpus page",
         "Q-2": "Q-2's own corpus page"}))


def _write_synthetic_batch(
        directory: Path, name: str,
        questions: dict[str, str],
        missing: str | None = None
        ) -> Path:
    """Write a synthetic frozen batch - one F2 question per
    entry, each with its own single corpus page - and return
    its directory; the caller loads it (a batch whose manifest
    does not register a field is not a frozen batch, and the
    refusal test's batch names the field it leaves out).

    ``missing`` names a manifest field to leave unregistered
    (the refusal test's batch). The manifest registers its
    paths batch-dir-relative, the way a synthetic batch's
    manifest does (the frozen batches register repo-relative
    paths; `load_batch`'s resolution carries both)."""
    batch_dir = directory
    (batch_dir / "corpus").mkdir(parents=True)
    candidates: list[dict[str, Any]] = []
    corpus: dict[str, dict[str, Any]] = {}
    families: dict[str, str] = {}
    for question_id, page_text in questions.items():
        candidates.append({
            "id": question_id, "family": "F2",
            "request": f"{question_id}'s request",
            "requirements": [],
            "reference_design": {}, "worked_solution": "",
            "wrong_designs": [], "difficulty_rationale": ""})
        page = batch_dir / "corpus" / f"{question_id}-page.md"
        page.write_text(page_text, encoding="utf-8")
        corpus[question_id] = {
            "pages": [str(page.relative_to(batch_dir))],
            "sha256": hashlib.sha256(
                page.read_bytes()).hexdigest()}
        families[question_id] = "F2"
    manifest: dict[str, Any] = {
        "batch": name,
        "candidates": "candidates.json",
        "candidates_sha256": "",
        "corpus": corpus,
        "families": families,
        "calibration": {
            "units": ", ".join(
                f"D-pages on {question_id}"
                for question_id in questions),
            "ceiling_usd": 2.0},
        "pilot": {"ceiling_usd": 5.0,
                  "arms": {"F2": ["D-pages", "F", "E"]}},
        "per_unit_ceilings_usd": {
            "A": 0.15, "D": 0.4, "D-pages": 0.4,
            "F": 0.4, "E": 1.5},
        "deadline_seconds": 3600,
        "single_call_max_tokens": 32768}
    candidates_path = batch_dir / "candidates.json"
    candidates_path.write_text(
        json.dumps(candidates, indent=2) + "\n",
        encoding="utf-8")
    manifest["candidates_sha256"] = hashlib.sha256(
        candidates_path.read_bytes()).hexdigest()
    if missing is not None:
        del manifest[missing]
    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8")
    return batch_dir


# ── (c) The freeze guard ───────────────────────────────

class TestCFreezeGuard:
    """Both modes refuse to start unless a batch's candidates
    hash to the manifest's registered sha256, each question's
    corpus pages hash to the manifest's registered sha256 over
    the pages concatenated in the listed order, and docs/tier4/
    pages are byte-identical to the frozen pages they mirror."""

    @staticmethod
    def _flip(path: Path) -> None:
        """A one-byte change: the first byte, flipped."""
        data = bytearray(path.read_bytes())
        data[0] = data[0] ^ 0x01
        path.write_bytes(bytes(data))

    @pytest.fixture
    def frozen_copy(self):
        """A tmp copy of the pilot batch, its manifest's
        registered paths rewritten batch-dir-relative (the
        synthetic-batch convention), so the copy's paths
        resolve to the copy, not the frozen tree."""
        tmp = Path(tempfile.mkdtemp())
        pilot = tmp / "pilot"
        shutil.copytree(runner.TIER4 / "pilot", pilot)
        _rewrite_manifest_paths(pilot)
        try:
            yield pilot, runner.load_batch(pilot)
        finally:
            shutil.rmtree(tmp)

    @pytest.fixture
    def frozen_batch2_copy(self):
        """The same, for batch 2 - whose corpus carries two
        questions' pages, one each."""
        tmp = Path(tempfile.mkdtemp())
        batch2 = tmp / "batch2"
        shutil.copytree(runner.TIER4 / "batch2", batch2)
        _rewrite_manifest_paths(batch2)
        try:
            yield batch2, runner.load_batch(batch2)
        finally:
            shutil.rmtree(tmp)

    @pytest.fixture
    def docs_copy(self):
        """A tmp copy of docs/tier4/, bound as the mirror the
        freeze guard compares the mirrored pages against."""
        tmp = Path(tempfile.mkdtemp())
        docs = tmp / "tier4"
        shutil.copytree(runner.DOCS_TIER4, docs)
        saved = runner.DOCS_TIER4
        runner.DOCS_TIER4 = docs
        try:
            yield docs
        finally:
            runner.DOCS_TIER4 = saved
            shutil.rmtree(tmp)

    def test_the_guard_holds_on_the_frozen_tree(self):
        """Both frozen batches as they stand: no refusals, and
        the measured hashes are the manifests' registered
        values.

        Break-proof: change a batch's registered
        candidates_sha256 by one hex digit, and the assert
        fails - the measured hash no longer equals the
        registered one."""
        assert runner.check_freeze(PILOT) == []
        assert runner.check_freeze(BATCH2) == []
        assert runner.batch_sha256(PILOT) == PILOT.candidates_sha256
        assert runner.batch_sha256(BATCH2) == (
            BATCH2.candidates_sha256)
        for question_id in PILOT.corpus:
            assert runner.corpus_sha256(
                question_id, PILOT) == PILOT.corpus_sha256[question_id]
        for question_id in BATCH2.corpus:
            assert runner.corpus_sha256(
                question_id, BATCH2) == (
                BATCH2.corpus_sha256[question_id])

    def test_a_one_byte_change_to_candidates_json_refuses(
            self, frozen_copy):
        """Break-proof: change `check_freeze` to compare only the
        corpus, and this test fails with no refusal for the
        mutated batch file."""
        _pilot, batch = frozen_copy
        self._flip(batch.candidates_path)
        refusals = runner.check_freeze(batch)
        assert refusals
        assert any("candidates.json" in refusal
                    for refusal in refusals), refusals

    def test_a_one_byte_change_to_a_corpus_page_refuses(
            self, frozen_copy):
        """Break-proof: change `check_freeze` to skip the corpus
        hash, and this test fails - the docs-copy comparison
        still fires, but the corpus's own hash refusal is gone."""
        _pilot, batch = frozen_copy
        page = batch.corpus["T4-06"][0]
        self._flip(page)
        refusals = runner.check_freeze(batch)
        assert refusals
        assert any("corpus" in refusal for refusal in refusals)
        assert any(page.name in refusal
                    for refusal in refusals), refusals

    def test_a_one_byte_change_to_a_docs_copy_refuses(
            self, frozen_copy, docs_copy):
        """Break-proof: change `check_freeze` to compare the docs
        copies by name only, and this test fails with no
        refusal."""
        _pilot, batch = frozen_copy
        self._flip(docs_copy / "T4-06-vortexia-2.md")
        refusals = runner.check_freeze(batch)
        assert refusals
        assert any("T4-06-vortexia-2.md" in refusal
                    for refusal in refusals), refusals

    def test_a_deleted_docs_copy_refuses(
            self, frozen_copy, docs_copy):
        """Break-proof: change `check_freeze` to test only
        `docs_copy.exists()`, and a truncated copy would pass -
        the byte comparison is the guard."""
        _pilot, batch = frozen_copy
        (docs_copy / "T4-06-vortexia-3.md").unlink()
        refusals = runner.check_freeze(batch)
        assert refusals
        assert any("T4-06-vortexia-3.md" in refusal
                    for refusal in refusals), refusals

    def test_batch2s_guard_refuses_a_one_byte_change_to_its_candidates(
            self, frozen_batch2_copy):
        """Batch 2's own registration (R9): a one-byte change to
        its candidates refuses, naming the file.

        Break-proof: change `check_freeze` to hash the candidates
        of the default batch whatever batch is named, and this
        test fails - the copy's own registered sha256 would
        never be compared."""
        _batch2, batch = frozen_batch2_copy
        self._flip(batch.candidates_path)
        refusals = runner.check_freeze(batch)
        assert refusals
        assert any("candidates.json" in refusal
                    for refusal in refusals), refusals

    def test_batch2s_guard_refuses_a_one_byte_change_to_either_corpus_page(
            self, frozen_batch2_copy):
        """Batch 2's corpus carries two questions' pages, one
        each: a one-byte change to either refuses, naming the
        question and its page.

        Break-proof: change `corpus_sha256` to hash only the
        first page of the listed order, and the second page's
        assert fails - a moved page would hash to the registered
        figure."""
        _batch2, batch = frozen_batch2_copy
        for question_id in ("T4-15", "T4-16"):
            page = batch.corpus[question_id][0]
            original = page.read_bytes()
            self._flip(page)
            try:
                refusals = runner.check_freeze(batch)
            finally:
                page.write_bytes(original)
            assert refusals, question_id
            # Every refusal names the moved question and its
            # page - and only the moved question: the other
            # question's pages still hash to their registered
            # sha256.
            assert all(question_id in refusal
                       for refusal in refusals), (
                question_id, refusals)
            assert any(page.name in refusal
                       for refusal in refusals), (
                question_id, refusals)

    def test_both_modes_refuse_to_start_when_the_guard_fails(
            self, frozen_copy):
        """The refusal is the modes' own: `run_tier4_experiment`
        raises `ExperimentRefused` naming the drifted file, before
        any gate or network call.

        Break-proof: move the freeze check after the gate check in
        `run_tier4_experiment`, and this test fails - the gate's
        refusal, not the freeze's, is raised first."""
        _pilot, batch = frozen_copy
        self._flip(batch.candidates_path)
        with pytest.raises(runner.ExperimentRefused) as refused:
            asyncio.run(runner.run_tier4_experiment(
                "calibration",
                client_factory=_no_client_factory(),
                catalogue=runner._dry_run_catalogue(
                    runner.DRY_RUN_SERVINGS),
                credit=runner.DRY_RUN_CREDIT,
                batch=batch))
        assert any("candidates.json" in refusal
                    for refusal in refused.value.detail), (
            refused.value.detail)


def _rewrite_manifest_paths(batch_dir: Path) -> None:
    """Rewrite a copied batch's manifest so its registered paths
    are batch-dir-relative - the copy's paths then resolve to
    the copy (the frozen manifests register repo-relative
    paths, which would resolve to the frozen tree)."""
    manifest = json.loads(
        (batch_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["candidates"] = str(
        Path(manifest["candidates"]).name)
    for entry in manifest["corpus"].values():
        entry["pages"] = [
            str(Path("corpus") / Path(page).name)
            for page in entry["pages"]]
    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8")


def _no_client_factory():
    """A client factory that cannot be reached: the dry run's
    refusals happen before any client exists, so a factory that
    raises proves the refusal came first."""
    def factory(*_args, **_kwargs):
        raise AssertionError("no client may exist before the "
                             "preflight clears")
    return factory


# ── (d) The plan ───────────────────────────────────────

class TestDPlan:
    """The calibration plans exactly its batch's units; the pilot
    plans the named ids x their family's arms and refuses what
    it cannot run."""

    def test_the_calibration_plans_exactly_nine_units(self):
        """A on T4-02..T4-05, D on T4-02..T4-05, D-pages on
        T4-06, one repetition each - and the seeded interleaved
        order is the one an independent reconstruction of the
        enumeration and the registered seed produces (the guard
        test's own discipline).

        Break-proof: change `CALIBRATION_SEED`, and the order
        assert fails; change the enumeration to `for arm ... for
        question ...`, and the order's digest fails."""
        assert len(CALIBRATION) == 9
        assert sorted((unit[0], unit[2]) for unit in CALIBRATION) == (
            sorted(
                [(question_id, arm)
                 for question_id in PILOT.f1_ids
                 for arm in runner.CALIBRATION_ARMS_F1]
                + [("T4-06", "D-pages")]))
        # The independent reconstruction: the same enumeration and
        # the same seed, built here from the registered constants.
        units: list[list[Any]] = [
            [question_id, 1, arm]
            for question_id in PILOT.f1_ids
            for arm in runner.CALIBRATION_ARMS_F1]
        units += [["T4-06", 1, arm]
                  for arm in runner.CALIBRATION_ARMS_F2]
        random.Random(runner.CALIBRATION_SEED).shuffle(units)
        assert CALIBRATION == units
        assert runner._order_digest(CALIBRATION) == (
            runner._order_digest(units))

    def test_the_batch2_calibration_plans_exactly_its_two_d_pages_units(
            self):
        """`plan calibration --batch evals/tier4/batch2`: D-pages
        on T4-15 and T4-16, one repetition each - the batch's
        own registration (R9), not a code path. Batch 2 has no
        F1 questions, so its calibration plan carries no A or D
        unit.

        Break-proof: change `calibration_plan` to run the F1
        arms on every batch whatever its families, and the
        unit-count assert fails - the plan would name units
        the batch cannot run."""
        plan = runner.calibration_plan(BATCH2)
        assert len(plan) == 2
        assert sorted((unit[0], unit[2]) for unit in plan) == [
            ("T4-15", "D-pages"), ("T4-16", "D-pages")]
        assert all(unit[1] == 1 for unit in plan)
        # The seeded order, reconstructed independently.
        units = [["T4-15", 1, "D-pages"],
                 ["T4-16", 1, "D-pages"]]
        random.Random(runner.CALIBRATION_SEED).shuffle(units)
        assert plan == units

    def test_the_pilot_plans_the_named_ids_x_their_family_arms(
            self):
        """Four named ids - three F1, one F2 - x their
        family's arms: 4 + 4 + 4 + 3 = 15 units, in the seeded
        interleaved order, reconstructed independently.

        Break-proof: change `PILOT_SEED`, and the digest assert
        fails; change the batch's pilot arm registration, and the
        unit-count assert fails."""
        assert len(PILOT_PLAN) == 15
        counts: dict[str, int] = {}
        for unit in PILOT_PLAN:
            counts[unit[2]] = counts.get(unit[2], 0) + 1
        assert counts == {"A": 3, "D": 3, "D-pages": 1, "E": 4,
                          "F": 4}
        units: list[list[Any]] = []
        for question_id in ("T4-02", "T4-03", "T4-04", "T4-06"):
            family = QUESTIONS[question_id]["family"]
            for arm in runner.family_arms(family, "pilot", PILOT):
                units.append([question_id, 1, arm])
        random.Random(runner.PILOT_SEED).shuffle(units)
        assert PILOT_PLAN == units

    def test_the_pilot_refuses_more_than_the_registered_limit(
            self):
        """Break-proof: change `PILOT_ID_LIMIT` to 5, and the
        refusal disappears - the limit is the registered constant,
        not a count the plan happens to produce."""
        order, refusals = runner.pilot_plan(
            ["T4-02", "T4-03", "T4-04", "T4-05", "T4-06"], PILOT)
        assert order == []
        assert any("limit" in refusal for refusal in refusals)

    def test_the_pilot_refuses_an_id_outside_the_batch(
            self):
        """Break-proof: change `pilot_plan` to skip unknown ids
        instead of refusing, and the refusal disappears and the
        plan runs four units - the frozen batch is the plan's
        population."""
        order, refusals = runner.pilot_plan(
            ["T4-02", "T4-99"], PILOT)
        assert order == []
        assert any("not in the frozen batch" in refusal
                    for refusal in refusals), refusals

    def test_the_pilot_refuses_an_f2_id_with_arm_a(
            self):
        """Arm A does not run on F2 (the command's constraint):
        an explicit arm restriction naming it is refused, not
        silently skipped.

        Break-proof: change `pilot_plan` to `continue` past an
        arm the family does not run, and the refusal disappears -
        the unit would be dropped silently, a plan the owner
        never saw."""
        order, refusals = runner.pilot_plan(
            ["T4-06"], arms=("A",), batch=PILOT)
        assert order == []
        assert any("arm A does not run" in refusal
                    for refusal in refusals), refusals

    def test_the_pilot_refuses_a_repeated_id(
            self):
        """Break-proof: remove the repetition check, and the plan
        runs the id's arms twice - a repetition the owner did not
        name."""
        order, refusals = runner.pilot_plan(
            ["T4-02", "T4-02"], PILOT)
        assert order == []
        assert any("twice" in refusal for refusal in refusals)


# ── (e) The gate and the preflight ─────────────────────

class TestEGateAndPreflight:
    """The gate is R4's: TIER3_SPEND_AUTHORIZED equals the
    mode's registered ceiling exactly. The preflight prints each
    arm's per-call and per-unit worst case at the batch's
    registered max_tokens (R8), prints each single-call arm's
    provider pin (R7), and refuses an arm with no pin."""

    @staticmethod
    def _settings(authorized: str | None, fingerprint: str):
        """A stand-in for the tier-3 settings the gate reads: the
        ratified fingerprint pin and the spend authorization."""
        servings = runner.DRY_RUN_SERVINGS

        class _Settings:
            tier3_servings_ratified = fingerprint
            tier3_arm_a = servings["A"]
            tier3_arm_d = servings["D"]
            tier3_spend_authorized = authorized

        return _Settings()

    def test_the_calibration_refuses_at_5_00_and_accepts_2_00(
            self):
        """R4 both ways: the pilot calibration's gate clears at
        $2.00 and refuses at $5.00, naming the ceiling; the
        pilot's gate clears at $5.00 and refuses at $2.00.

        Break-proof: change the gate's comparison to
        `authorized >= ceiling`, and the $5.00 calibration case
        clears - an authorization above the ceiling would spend
        past a plan the owner never ratified."""
        servings = runner.DRY_RUN_SERVINGS
        fingerprint = runner._servings_fingerprint(servings)
        calibration = self._settings("2.00", fingerprint)
        pilot = self._settings("5.00", fingerprint)
        assert runner.tier4_gate_report(
            calibration, servings, fingerprint,
            PILOT.calibration_ceiling, "calibration") == []
        assert runner.tier4_gate_report(
            pilot, servings, fingerprint,
            PILOT.pilot_ceiling, "pilot") == []
        for authorized in ("5.00", None, "abc"):
            missing = runner.tier4_gate_report(
                self._settings(authorized, fingerprint),
                servings, fingerprint,
                PILOT.calibration_ceiling, "calibration")
            assert missing, authorized
            assert any("TIER3_SPEND_AUTHORIZED" in refusal
                        for refusal in missing), missing
        for authorized in ("2.00", "5.01", None):
            missing = runner.tier4_gate_report(
                self._settings(authorized, fingerprint),
                servings, fingerprint,
                PILOT.pilot_ceiling, "pilot")
            assert missing, authorized
            assert any("TIER3_SPEND_AUTHORIZED" in refusal
                        for refusal in missing), missing

    def test_the_batch2_gate_accepts_1_00_and_refuses_2_00(
            self):
        """R4 on batch 2's own registration: the calibration's
        gate clears at the batch's registered $1.00 and refuses
        at $2.00, naming the ceiling.

        Break-proof: change the gate's comparison to
        `authorized >= ceiling`, and the $2.00 case clears - an
        authorization above the ceiling would spend past a plan
        the owner never ratified."""
        servings = runner.DRY_RUN_SERVINGS
        fingerprint = runner._servings_fingerprint(servings)
        accepts = self._settings("1.00", fingerprint)
        refuses = self._settings("2.00", fingerprint)
        assert runner.tier4_gate_report(
            accepts, servings, fingerprint,
            BATCH2.calibration_ceiling, "calibration") == []
        missing = runner.tier4_gate_report(
            refuses, servings, fingerprint,
            BATCH2.calibration_ceiling, "calibration")
        assert missing
        assert any("TIER3_SPEND_AUTHORIZED" in refusal
                    for refusal in missing), missing

    def test_the_gate_refuses_a_fingerprint_that_is_not_ratified(
            self):
        """The servings map is the owner's standing pins, refused
        when the ratified fingerprint names another map.

        Break-proof: change `tier4_gate_report` to skip the
        fingerprint check, and this test fails with no refusal."""
        servings = runner.DRY_RUN_SERVINGS
        fingerprint = runner._servings_fingerprint(servings)
        settings = self._settings("2.00", "deadbeef")
        missing = runner.tier4_gate_report(
            settings, servings, fingerprint,
            PILOT.calibration_ceiling, "calibration")
        assert any("TIER3_SERVINGS_RATIFIED" in refusal
                    for refusal in missing), missing

    def test_the_credit_preflight_refuses_below_the_mode_ceiling(
            self):
        """The mocked balance below the mode's ceiling refuses,
        naming the shortfall; at the ceiling it clears; a balance
        that could not be read is no evidence and refuses.

        Break-proof: change the comparison to `credit <= ceiling`,
        and the at-the-ceiling case refuses - or to
        `credit is None` passing, and the unreadable-balance case
        clears, a paid run that cannot establish its balance."""
        servings = runner.DRY_RUN_SERVINGS
        catalogue = runner._dry_run_catalogue(servings)
        with runner.tier4_pins(runner.DRY_RUN_PROVIDER_ORDER):
            for batch, mode in ((PILOT, "calibration"),
                                  (PILOT, "pilot"),
                                  (BATCH2, "calibration"),
                                  (BATCH2, "pilot")):
                ceiling = (batch.calibration_ceiling
                           if mode == "calibration"
                           else batch.pilot_ceiling)
                below = runner.tier4_preflight(
                    servings, catalogue, credit=ceiling - 0.01,
                    ceiling=ceiling,
                    arms=runner.mode_arms(mode, batch),
                    questions=batch.questions(),
                    mode=mode, batch=batch)
                assert any("remaining credit" in refusal
                            for refusal in below.refusals), (
                    batch.name, mode, below.refusals)
                at = runner.tier4_preflight(
                    servings, catalogue, credit=ceiling,
                    ceiling=ceiling,
                    arms=runner.mode_arms(mode, batch),
                    questions=batch.questions(),
                    mode=mode, batch=batch)
                assert not any("remaining credit" in refusal
                                for refusal in at.refusals), (
                    batch.name, mode, at.refusals)
                unreadable = runner.tier4_preflight(
                    servings, catalogue, credit=None,
                    ceiling=ceiling,
                    arms=runner.mode_arms(mode, batch),
                    questions=batch.questions(),
                    mode=mode, batch=batch)
                assert any("could not be read" in refusal
                            for refusal in unreadable.refusals), (
                    batch.name, mode, unreadable.refusals)

    def test_the_preflight_prints_each_arms_worst_case(self):
        """Every arm the pilot runs - A, D, D-pages, F, E - has
        its per-call and per-unit worst case in the preflight's
        reports, at the fixture catalogue's shape and the batch's
        registered max_tokens: the single-call arms' one call at
        32768 against its per-unit ceiling, arm F's per-tier
        calls and its sequence, arm E's per-tier calls.

        Break-proof: change `_single_call_worst_case` to compute
        at the tier-3 registered 8000 tokens, and the
        max_tokens assert fails - the printed figure would be
        the void calibration's budget, not the registered one."""
        servings = runner.DRY_RUN_SERVINGS
        catalogue = runner._dry_run_catalogue(servings)
        with runner.tier4_pins(runner.DRY_RUN_PROVIDER_ORDER):
            report = runner.tier4_preflight(
                servings, catalogue, credit=runner.DRY_RUN_CREDIT,
                ceiling=PILOT.pilot_ceiling,
                arms=runner.mode_arms("pilot", PILOT),
                questions=QUESTIONS, mode="pilot", batch=PILOT)
        assert report.refusals == []
        printed = "\n".join(report.reports)
        for arm in ("A", "D", "D-pages"):
            assert f"arm {arm}: one call" in printed, printed
            assert f"${PILOT.per_unit_ceilings[runner.ceiling_key(arm)]:.2f}" \
                in printed
        for tier in ("triage", "research", "search",
                     "engineering", "judge"):
            assert f"arm F/{tier}:" in printed, printed
            assert f"arm E/{tier}:" in printed, printed
        # The single-call budget is the batch's registration
        # (R8), stated on the printed figure.
        assert (f"max_tokens {PILOT.single_call_max_tokens}"
                in printed), printed
        # The per-call and per-unit figures are stated, not
        # implied: every figure line carries a worst case and
        # a ceiling, and every informational line names the
        # order in force (a pin, or a provider order).
        for line in report.reports:
            assert ("worst case" in line
                    or "pinned to" in line
                    or "provider order" in line), line
        for line in report.reports:
            if "worst case" in line:
                assert "ceiling" in line, line

    def test_the_preflight_prints_each_single_call_arms_pin(
            self):
        """Every single-call arm's pin is printed - the owner's
        ratified tier3_arm_a/tier3_arm_d entries, re-keyed to
        the tier-4 functions the arms bill to (R7), and the
        pipeline arms' per-tier orders informationally.

        Break-proof: change the pin case to print the arm's
        serving instead of its pin, and the pin asserts fail -
        the printed line would name the serving, not the pin the
        call carries."""
        servings = runner.DRY_RUN_SERVINGS
        catalogue = runner._dry_run_catalogue(servings)
        with runner.tier4_pins(runner.DRY_RUN_PROVIDER_ORDER):
            report = runner.tier4_preflight(
                servings, catalogue, credit=runner.DRY_RUN_CREDIT,
                ceiling=PILOT.pilot_ceiling,
                arms=runner.mode_arms("pilot", PILOT),
                questions=QUESTIONS, mode="pilot", batch=PILOT)
        assert report.refusals == []
        printed = "\n".join(report.reports)
        for arm, pin in (("A", servings["A"]),
                         ("D", servings["D"]),
                         ("D-pages", servings["D"])):
            assert f"arm {arm}: pinned to {pin}" in printed, printed
        # The pipeline arms' per-tier orders are printed
        # informationally, every tier the modes' arms run on.
        for tier in ("E", "F"):
            assert f"arm {tier}/" in printed, printed

    def test_the_preflight_refuses_an_arm_with_no_pin(self):
        """A provider-order line that registers no tier3 pin -
        the owner's general list alone, the void calibration's
        configuration - refuses every single-call arm: an arm
        with no pin would run on the line's general list, which
        is what served the void calibration (R7).

        Break-proof: change the pin case to fall back to the
        general list instead of refusing, and the refusals
        disappear - the run would start on unpinned servings."""
        servings = runner.DRY_RUN_SERVINGS
        catalogue = runner._dry_run_catalogue(servings)
        with runner.tier4_pins("general:dryrun/arm-a"):
            report = runner.tier4_preflight(
                servings, catalogue, credit=runner.DRY_RUN_CREDIT,
                ceiling=PILOT.calibration_ceiling,
                arms=("A", "D", "D-pages"),
                questions=QUESTIONS,
                mode="calibration", batch=PILOT)
        for arm in ("A", "D", "D-pages"):
            assert any(
                f"arm {arm}: no provider pin" in refusal
                for refusal in report.refusals), (
                arm, report.refusals)
        # The refusal names the pin key the arm's call bills to.
        assert any("tier4_arm_a" in refusal
                    for refusal in report.refusals)
        assert any("tier4_arm_d" in refusal
                    for refusal in report.refusals)


# ── (j) The paid path's pin source (R7) ──────────────

class TestPinSource:
    """The tier-4 paid path's pin source (R7): the
    ratified provider-order line is read from the paid
    runners' own config file (.env.tier3), where the
    owner ratified the tier3_arm_a/tier3_arm_d entries -
    not from the ambient line the routing layer reads
    from .env, which registers no tier3_arm_* entries.

    Measured 2026-10-17: the live preflight refused arm
    D-pages on exactly that gap, at zero spend - the
    owner's .env line carries the workflow tiers' pins
    and no arm entries, while the .env.tier3 line the
    owner ratified carries both."""

    AMBIENT = (
        "triage:google-ai-studio,engineering:together,"
        "architecture:xiaomi/fp8,escalation:inference-net/fp4,"
        "search:Perplexity,research:google-ai-studio,"
        "ranker:Fireworks,premium:,judge:google-vertex/us-south1")
    RATIFIED = (
        AMBIENT
        + ",tier3_arm_a:google-ai-studio,"
          "tier3_arm_b:google-ai-studio,"
          "tier3_arm_c_1:together,"
          "tier3_arm_c_2:inference-net/fp4,"
          "tier3_arm_d:inference-net/fp4")

    def test_the_ratified_line_is_read_from_the_file(
            self, tmp_path, monkeypatch):
        """The paid runners' config file is the pin
        source: an ambient export of the same variable -
        the .env line the routing layer reads, which
        registers no tier3_arm entries - does not shadow
        the file's ratified line, and an absent file
        reads as empty.

        Break-proof: change the helper to read the
        ambient environment (or any pydantic-settings
        read of the name, which the export shadows), and
        the first assert fails - the ambient line carries
        no tier3_arm_d entry to map."""
        monkeypatch.setenv(
            "OPENROUTER_PROVIDER_ORDER", self.AMBIENT)
        env_file = tmp_path / ".env.tier3"
        env_file.write_text(
            "TIER3_SPEND_AUTHORIZED=1.00\n"
            f"OPENROUTER_PROVIDER_ORDER={self.RATIFIED}\n",
            encoding="utf-8")
        assert runner._ratified_provider_order(
            env_file) == self.RATIFIED
        assert runner._ratified_provider_order(
            tmp_path / "absent.env") == ""

    def test_the_paid_path_pins_the_arms_from_the_ratified_file(
            self, tmp_path, monkeypatch):
        """The paid path's pin case, end to end: under
        the ambient line the routing layer reads (the
        owner's real .env shape - the workflow tiers'
        pins and no tier3_arm entries) the single-call
        arms are unpinned and the preflight refuses them
        - the live refusal, reproduced at zero spend;
        under the ratified line read from the paid
        runners' own file, the arms carry the owner's
        ratified pins and the pin case prints them (R7).

        Break-proof: wire the paid path's tier4_pins()
        to the ambient line again - the live defect this
        repair fixes - and the second block of asserts
        fails: the pins resolve empty and the preflight
        refuses the arms, as it did live."""
        servings = runner.DRY_RUN_SERVINGS
        catalogue = runner._dry_run_catalogue(servings)
        monkeypatch.setenv(
            "OPENROUTER_PROVIDER_ORDER", self.AMBIENT)
        env_file = tmp_path / ".env.tier3"
        env_file.write_text(
            "TIER3_SPEND_AUTHORIZED=2.00\n"
            f"OPENROUTER_PROVIDER_ORDER={self.RATIFIED}\n",
            encoding="utf-8")
        saved = runner.harness_settings.openrouter_provider_order
        try:
            # The ambient line alone: the mapping re-keys
            # nothing, the arms are unpinned, and the
            # preflight refuses them - an unpinned arm
            # never falls to the general list (R7).
            runner.harness_settings.openrouter_provider_order = (
                self.AMBIENT)
            with runner.tier4_pins():
                assert runner._arm_pin("A") == []
                assert runner._arm_pin("D-pages") == []
                report = runner.tier4_preflight(
                    servings, catalogue,
                    credit=runner.DRY_RUN_CREDIT,
                    ceiling=PILOT.calibration_ceiling,
                    arms=("A", "D", "D-pages"),
                    questions=QUESTIONS,
                    mode="calibration", batch=PILOT)
            for arm in ("A", "D", "D-pages"):
                assert any(
                    f"arm {arm}: no provider pin" in refusal
                    for refusal in report.refusals), (
                    arm, report.refusals)
            # The ratified line, read from the file: the
            # arms carry the owner's ratified pins and
            # the pin case prints them.
            with runner.tier4_pins(
                    runner._ratified_provider_order(env_file)):
                assert runner._arm_pin("A") == [
                    "google-ai-studio"]
                assert runner._arm_pin("D") == [
                    "inference-net/fp4"]
                assert runner._arm_pin("D-pages") == [
                    "inference-net/fp4"]
                report = runner.tier4_preflight(
                    servings, catalogue,
                    credit=runner.DRY_RUN_CREDIT,
                    ceiling=PILOT.calibration_ceiling,
                    arms=("A", "D", "D-pages"),
                    questions=QUESTIONS,
                    mode="calibration", batch=PILOT)
        finally:
            runner.harness_settings.openrouter_provider_order = (
                saved)
        assert report.refusals == []
        printed = "\n".join(report.reports)
        assert "arm A: pinned to google-ai-studio" in printed
        assert "arm D: pinned to inference-net/fp4" in printed
        assert "arm D-pages: pinned to inference-net/fp4" in printed


# ── (f) The mocked dry run ─────────────────────────────

class TestFDryRun:
    """The mocked dry run of both modes of both batches: zero
    spend, every record field, the arm-blind reading sheet, every
    failure class the command names at least once per mode, and
    the void calibration's two defect classes recorded (R7, R8)."""

    def test_both_modes_run_at_zero_spend(self):
        """Both modes of both batches stay inside each mode's
        registered ceiling - the scripted clients bill through
        the real guard and accounting, so the figures are the
        real arithmetic at the fixture rates, and no network
        call happens (the suite's guard refuses every
        non-loopback socket).

        Break-proof: change `DRY_RUN_CREDIT` to a figure below a
        mode's ceiling, and the dry run refuses to start - the
        credit preflight is the real one."""
        for batch_name, batch in (("pilot", PILOT),
                                  ("batch2", BATCH2)):
            for mode in ("calibration", "pilot"):
                result = _outcome(batch_name, mode)
                ceiling = (batch.calibration_ceiling
                           if mode == "calibration"
                           else batch.pilot_ceiling)
                assert result["budget"]["spent"] <= ceiling, (
                    batch_name, mode, result["budget"])
                assert result["budget"]["cap"] == ceiling
                # Every unit the plan names is a record: nothing
                # ran twice and nothing was dropped.
                assert len(result["records"]) == result["order_units"]

    def test_the_header_carries_the_registered_figures(self):
        """The results header carries the batch's own
        registration (R9): its name, its directory, the batch
        sha256, each question's corpus sha256, the mode, the
        order digest, the servings fingerprint, the ceilings, the
        authorization, the single-call max_tokens and the
        deadline - the figures the command's RECORDS constraint
        names.

        Break-proof: drop `corpus_sha256` from the log's config,
        and the assert fails; drop `max_tokens`, and the R8
        assert fails."""
        for batch_name, batch in (("pilot", PILOT),
                                  ("batch2", BATCH2)):
            for mode in ("calibration", "pilot"):
                path = Path(_outcome(batch_name, mode)["path"])
                header = json.loads(
                    path.read_text(encoding="utf-8").splitlines()[0])
                assert header["record"] == "header"
                assert header["mode"] == mode
                assert header["manifest_version"] == (
                    runner.TIER4_MANIFEST_VERSION)
                assert header["dataset_version"] == (
                    batch.dataset_version)
                assert header["batch"] == batch.name
                assert header["batch_dir"] == batch.batch_dir
                assert header["batch_sha256"] == (
                    runner.batch_sha256(batch))
                assert header["corpus_sha256"] == {
                    question_id: runner.corpus_sha256(
                        question_id, batch)
                    for question_id in batch.corpus}
                assert header["servings_fingerprint"] == (
                    runner._servings_fingerprint(
                        runner.DRY_RUN_SERVINGS))
                assert header["authorization_ceiling"] == (
                    batch.calibration_ceiling if mode == "calibration"
                    else batch.pilot_ceiling)
                assert header["ceilings"] == dict(
                    batch.per_unit_ceilings)
                assert header["max_tokens"] == (
                    batch.single_call_max_tokens)
                assert header["deadline_seconds"] == (
                    batch.deadline_seconds)
                assert header["order_units"] == (
                    _outcome(batch_name, mode)["order_units"])
                assert header["order_sha256"] == (
                    _outcome(batch_name, mode)["order_sha256"])

    def test_the_records_carry_every_field(self):
        """Every unit record carries the command's RECORDS fields:
        question id, family, arm, profile, the exact user
        message's sha256, the R7/R8 flags, and the tier-3 unit
        record fields (status, answer, candidate, iterations,
        reason, stop_reason, calls, cost, seconds).

        Break-proof: drop `message_sha256` from
        `tier4_unit_record`, and the assert fails; drop the
        pipeline record's surfacing of `candidate`, and that
        assert fails."""
        fields = ("question_id", "repetition", "family", "arm",
                  "profile", "message_sha256", "status", "answer",
                  "candidate", "iterations", "reason", "stop_reason",
                  "calls", "cost", "seconds", "serving", "delivered",
                  "serving_pins", "serving_mismatch", "truncated")
        for batch_name in ("pilot", "batch2"):
            for mode in ("calibration", "pilot"):
                for record in _outcome(
                        batch_name, mode)["records"]:
                    for field in fields:
                        assert field in record, (
                            batch_name, mode, field)
        # The D-pages record's message sha256 is the composed
        # message's own, and the F2 records of F and E name the
        # tier-4 profile.
        calibration = _outcome("pilot", "calibration")["records"]
        d_pages = [record for record in calibration
                    if record["arm"] == "D-pages"]
        assert d_pages
        for record in d_pages:
            assert record["message_sha256"] == runner.message_sha256(
                "D-pages", QUESTIONS["T4-06"], PILOT)

    def test_the_reading_sheet_is_generated_and_arm_blind(self):
        """One entry per answered unit, in a seeded order, with no
        arm label: each entry carries the question's id, family,
        request and requirement statements - everything a reading
        needs - the delivered answer, and the R7/R8 flags.

        Break-proof: add the arm to the sheet's entries, and the
        arm-blind assert fails; drop the requirement statements,
        and the statements assert fails."""
        for batch_name in ("pilot", "batch2"):
            for mode in ("calibration", "pilot"):
                result = _outcome(batch_name, mode)
                sheet = _sheet(batch_name, mode)
                answered = [record for record in result["records"]
                            if record.get("answer")]
                assert sheet["units"] == len(answered)
                assert sheet["mode"] == mode
                assert len(sheet["entries"]) == len(answered)
                for entry in sheet["entries"]:
                    assert "arm" not in entry, entry
                    candidate = result["questions"][
                        entry["question_id"]]
                    assert entry["family"] == candidate["family"]
                    assert entry["request"] == candidate["request"]
                    assert [item["statement"]
                            for item in entry["requirement_statements"]
                            ] == [requirement["statement"]
                                  for requirement
                                  in candidate["requirements"]]
                    assert entry["answer"] in {
                        record["answer"] for record in answered}
                    # The flags ride the sheet: a boolean, never
                    # an absent field (convention 28).
                    assert isinstance(
                        entry["serving_mismatch"], bool), entry
                    assert isinstance(entry["truncated"], bool), entry
                    for field in ("reading_1", "reading_2",
                                  "resolution"):
                        assert entry[field] is None, entry

    def test_every_failure_class_appears_per_mode(self):
        """Each mode's census carries a refusal, a deadline, a
        provider failure and a budget stop - the four failure
        classes the command names, on the real fit rule and the
        real accounting.

        Break-proof: delete the budget-stop exhibit from
        `build_calibration_dry_run_script`, and the calibration's
        budget_stop count is zero - the class is included at least
        once because it is scripted, and the test fails."""
        # The pilot batch's scripts carry the failure-class
        # exhibits, one of each, in both modes.
        for mode in ("calibration", "pilot"):
            result = _outcome("pilot", mode)
            census = result["census"]
            assert census.get("refusal", 0) >= 1, (
                mode, census)
            assert census.get("deadline", 0) >= 1, (
                mode, census)
            assert census.get("budget_stop", 0) >= 1, (
                mode, census)
            provider_failures = [
                record for record in result["records"]
                if record["status"] == "incomplete"
                and str(record.get("stop_reason", "")).startswith(
                    "ProviderFailure")]
            assert provider_failures, (mode, census)
        # Batch 2's scripts run their units' defaults - its
        # plan carries no exhibit-keyed unit - so both of its
        # modes run clean: every unit delivered, no failure
        # class.
        for mode in ("calibration", "pilot"):
            result = _outcome("batch2", mode)
            statuses = {record["status"]
                        for record in result["records"]}
            assert statuses == {"delivered"}, (
                mode, statuses)
        # The exhibits are where the command's dry run puts them:
        # the calibration's budget stop is one call booking just
        # under the $2.00 authorization, refused by the unit's own
        # $0.40 ceiling after the call.
        calibration = _outcome("pilot", "calibration")["records"]
        booked = [record for record in calibration
                  if record["arm"] == "D"
                  and record["status"] == "incomplete"
                  and record["cost"] > PILOT.per_unit_ceilings["D"]]
        assert booked, calibration
        assert booked[0]["cost"] < PILOT.calibration_ceiling
        # The pilot's budget stop is composed: the ceiling-tail
        # defaults exhaust the $5.00 authorization inside the plan,
        # so the units after the crossing skip through the fit rule.
        pilot = _outcome("pilot", "pilot")
        assert pilot["census"]["budget_stop"] >= 1
        skipped = [record for record in pilot["records"]
                    if record["status"] == "skipped"]
        assert all("budget" in str(record.get("stop_reason", ""))
                    for record in skipped), skipped

    def test_the_two_defect_classes_the_void_calibration_ended_are_recorded(
            self):
        """The void calibration's two defect classes, each
        scripted into the dry run and each recorded (R7, R8): a
        call served from outside the arm's pin records
        serving_mismatch, and a call that ended on 'length'
        records truncated - both units delivered, both flagged on
        the reading sheet, neither counted readable.

        Break-proof: change `run_tier4_unit` to drop the
        serving_mismatch computation, and the mismatch asserts
        fail; change the truncated computation to test the answer's
        length instead of the finish reason, and the truncated
        asserts fail."""
        calibration = _outcome("pilot", "calibration")
        mismatch = [record for record in calibration["records"]
                    if record.get("serving_mismatch")]
        assert [record["question_id"] for record in mismatch] == ["T4-05"]
        assert mismatch[0]["status"] == "delivered"
        assert mismatch[0]["arm"] == "A"
        assert mismatch[0]["serving_pins"] == [
            runner.DRY_RUN_SERVINGS["A"]]
        truncated = [record for record in calibration["records"]
                     if record.get("truncated")]
        assert [record["question_id"] for record in truncated] == ["T4-06"]
        assert truncated[0]["status"] == "delivered"
        assert truncated[0]["arm"] == "D-pages"
        # Both flags ride the reading sheet.
        flags = {entry["question_id"]: entry
                 for entry in _sheet("pilot", "calibration")["entries"]}
        assert flags["T4-05"]["serving_mismatch"] is True
        assert flags["T4-06"]["truncated"] is True
        # Neither flagged unit is counted readable: no delivered
        # unit of the calibration is readable, and the summary
        # says so.
        readable = [record for record in calibration["records"]
                    if record.get("status") == "delivered"
                    and not record.get("truncated")
                    and not record.get("serving_mismatch")]
        assert readable == [], readable
        assert "arm A: 4 units" in calibration["summary"]
        assert "readable 0/4" in calibration["summary"]
        assert "arm D-pages: 1 units" in calibration["summary"]
        assert "readable 0/1" in calibration["summary"]

    def test_the_batch2_mocked_calibration_runs(self):
        """The mocked calibration dry run on batch 2 (the
        command's acceptance evidence): exactly its two D-pages
        units, both delivered, neither flagged - the batch's own
        plan, at the batch's own registrations.

        Break-proof: change `calibration_plan` to run the pilot
        batch's plan whatever batch is named, and the unit-count
        assert fails - batch 2's run would plan nine units."""
        batch2 = _outcome("batch2", "calibration")
        assert batch2["order_units"] == 2
        assert [(record["question_id"], record["arm"])
                for record in batch2["records"]] == [
                    ("T4-15", "D-pages"), ("T4-16", "D-pages")]
        assert all(record["status"] == "delivered"
                    for record in batch2["records"])
        assert not any(record.get("truncated")
                       or record.get("serving_mismatch")
                       for record in batch2["records"])
        # The header names batch 2's own registration.
        path = Path(batch2["path"])
        header = json.loads(
            path.read_text(encoding="utf-8").splitlines()[0])
        assert header["batch"] == "batch2"
        assert header["max_tokens"] == BATCH2.single_call_max_tokens

    def test_every_single_call_carries_its_pin_and_the_registered_budget(
            self):
        """The wiring proof (R7, R8): one A unit and one D unit
        through the unit executor, with a recording client - every
        call bills to the tier-4 function its arm's pin names
        (tier4_arm_a / tier4_arm_d, the re-keyed
        tier3_arm_a/tier3_arm_d entries), carries that pin's
        provider order, and runs at the batch's registered
        max_tokens.

        Break-proof: change `_tier4_execute_arm` to drop its
        max_tokens argument, and the budget assert fails at the
        tier-3 registered 8000; change `_map_tier4_pins` to skip
        the re-keying, and the provider-order assert fails - the
        call would carry the line's general list."""
        batch = PILOT
        servings = runner.DRY_RUN_SERVINGS
        script = runner.build_calibration_dry_run_script(batch)
        catalogue = runner._dry_run_catalogue(servings)
        rates = _rates(catalogue)
        context = tier3._DryRunContext()
        calls: list[dict[str, Any]] = []
        questions = batch.questions()
        budget = runner.SweepBudget(cap=batch.calibration_ceiling)
        overrides = {
            "TIER3_ARM_A": servings["A"],
            "TIER3_ARM_B": servings["B"],
            "TIER3_ARM_C_1": servings["C"][0],
            "TIER3_ARM_C_2": servings["C"][1],
            "TIER3_ARM_D": servings["D"],
            "TIER3_SERVINGS_RATIFIED": (
                runner._servings_fingerprint(servings)),
            "TIER3_SPEND_AUTHORIZED": (
                f"{batch.calibration_ceiling:.2f}"),
        }
        with runner._env_overrides(overrides), \
                runner._harness_pin_overrides(servings["E"]), \
                runner.tier4_pins(runner.DRY_RUN_PROVIDER_ORDER):
            runner._install_rates(catalogue)
            factory = _recording_factory(script, rates, context, calls)
            dispatcher = runner._dry_run_tool_dispatcher(
                script, context)
            for question_id, arm in (("T4-02", "A"), ("T4-03", "D")):
                asyncio.run(runner.run_tier4_unit(
                    (question_id, 1, arm), questions, servings,
                    budget, client_factory=factory,
                    tool_dispatcher=dispatcher,
                    batch=batch))
        assert len(calls) == 2
        assert calls[0]["function"] == "tier4_arm_a"
        assert calls[0]["max_tokens"] == batch.single_call_max_tokens
        assert calls[0]["provider_order"] == [servings["A"]]
        assert calls[1]["function"] == "tier4_arm_d"
        assert calls[1]["max_tokens"] == batch.single_call_max_tokens
        assert calls[1]["provider_order"] == [servings["D"]]

    def test_the_dry_run_is_resumable(self):
        """A second invocation of a mode re-reads its own records
        and runs nothing twice: the log's resume is the tier-3
        discipline, on the tier-4 plan.

        Break-proof: delete the `if key in recorded: continue`
        line from `run_tier4_experiment`, and the second run's
        file carries every unit twice - the unit count doubles."""
        result = asyncio.run(runner._tier4_dry_run_mode(
            "calibration",
            runner.build_calibration_dry_run_script()))
        assert len(result["records"]) == result["order_units"]
        path = Path(result["path"])
        lines = [line for line in
                 path.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
        unit_lines = [line for line in lines
                      if json.loads(line).get("record") == "unit"]
        assert len(unit_lines) == result["order_units"]


class _RecordingClient(tier3.DryRunClient):
    """A scripted client that records every call's function,
    completion budget and the provider order in force - the
    wiring proof's instrument (R7, R8). It bills through the
    real guard and accounting like every dry-run double
    (convention 7)."""

    def __init__(self, *args: Any,
                 calls: list[dict[str, Any]],
                 **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._recorded = calls

    async def chat(
            self, function: str, system_prompt: str,
            user_message: str,
            response_format: dict[str, Any] | None = None,
            temperature: float = 0.3,
            max_tokens: int = 16384,
            model: str | None = None,
            tools: list[dict[str, Any]] | None = None,
            tool_choice: str | None = None,
    ) -> tier3.ModelResponse:
        self._recorded.append({
            "function": function,
            "max_tokens": max_tokens,
            "provider_order": list(
                runner.provider_order_for(function)),
        })
        return await super().chat(
            function, system_prompt, user_message,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens, model=model,
            tools=tools, tool_choice=tool_choice)


def _recording_factory(script: tier3.DryRunScript,
                       rates: dict[str, tuple[float, float]],
                       context: tier3._DryRunContext,
                       calls: list[dict[str, Any]]):
    """The recording client factory: the dry run's own factory,
    building recording clients."""
    def factory(unit_key, arm, serving, ceiling, call_limit):
        context.unit_key = unit_key
        return _RecordingClient(
            script, unit_key, serving, rates, ceiling,
            call_limit, calls=calls)
    return factory


# ── (g) Tier 3 unchanged ───────────────────────────────

class TestGTier3Unchanged:
    """The one line the tier-4 import changed in the tier-3
    runner - the dry run's scenario dispatch, generalized from
    `startswith("tier3_f_")` to the `"_f_" in id` the arm
    executors' id grammar makes true for any prefix - keeps every
    tier-3 id dispatching to the same workflow, and dispatches the
    tier-4 ids the same way."""

    @staticmethod
    def _probe(scenario_id: str) -> float:
        """Run one scenario through the dry run's stand-in at the
        pipeline boundary, with a stub script whose F outcomes cost
        $0.04 and whose E outcomes cost $0.11: the returned cost
        names the workflow the id dispatched to."""
        class _StubScript:
            def arm_f_outcome(self, _scenario_id):
                return {"cost": 0.04, "calls": 4, "seconds": 45.0,
                        "verdicts": {}, "iterations": []}

            def arm_e_outcome(self, _scenario_id):
                return {"cost": 0.11, "calls": 14, "seconds": 95.0,
                        "verdicts": {}, "iterations": []}

        scenario = tier3.Scenario(
            id=scenario_id, request="probe",
            description="the dispatch probe", workflow=None,
            timeout=1.0, expect={})
        stand_in = tier3.DryRunScenarioRunner(_StubScript())
        run = asyncio.run(stand_in(
            scenario, None, None, {}, timeout=1.0,
            max_spend=0.10, budget=None))
        return run.cost

    def test_the_tier3_ids_dispatch_to_their_own_workflows(self):
        """The tier-3 dry run's own ids still dispatch the way
        they did: a `tier3_f_` id runs the verify-first workflow's
        stand-in, a `tier3_e_` id the standing workflow's.

        Break-proof: change the dispatch back to
        `startswith("tier4_f_")`, and the tier3_f_ probe fails -
        it would read the standing workflow's outcome."""
        assert self._probe("tier3_f_Q6_r1") == 0.04
        assert self._probe("tier3_e_Q6_r1") == 0.11

    def test_the_tier4_ids_dispatch_the_same_way(self):
        """The tier-4 scenario ids the tier-4 runner builds
        (`tier4_e_...`, `tier4_f_...`) dispatch to the same two
        workflows - the generalization the tier-4 import needs.

        Break-proof: change the dispatch to
        `scenario.id.startswith("tier3_f_")`, and the tier4_f_
        probe fails - it would read the standing workflow's
        outcome, and every tier-4 F unit of the dry run would
        report the standing workflow's figures."""
        assert self._probe("tier4_f_T4-02_r1") == 0.04
        assert self._probe("tier4_e_T4-02_r1") == 0.11


# ── (h) The provider pins (R7) ─────────────────────────

class TestHProviderPins:
    """The single-call arms run on the owner's ratified
    tier3_arm_a/tier3_arm_d pins (R7): the mapping re-keys them
    to the tier-4 functions the arms bill to, a missing pin maps
    to an explicitly empty entry, and the pin context installs
    the mapped line for the run's duration."""

    def test_the_mapping_rekeys_the_owner_pins(self):
        """The owner's line, extended: the tier3_arm_a and
        tier3_arm_d entries re-keyed to the tier-4 functions the
        single-call arms bill to, every other entry kept in place.

        Break-proof: change the mapping to copy the general
        list's providers into the tier-4 entries, and the assert
        fails - the tier-4 entries would name the general list's
        providers, not the ratified pins."""
        mapped = runner._map_tier4_pins(
            "tier3_arm_a:StreamLake,tier3_arm_d:Wafer,"
            "general:Together")
        assert mapped == (
            "tier3_arm_a:StreamLake,tier3_arm_d:Wafer,"
            "general:Together,"
            "tier4_arm_a:StreamLake,tier4_arm_d:Wafer")

    def test_the_mapping_maps_a_missing_pin_to_an_empty_entry(self):
        """A line with no tier3 counterpart maps to an explicitly
        empty tier-4 entry - unpinned, refused by the preflight -
        never an absent key, which would fall to the general list
        (the void calibration's defect).

        Break-proof: change the mapping to skip the tier-4 entry
        when the tier3 counterpart is absent, and the assert
        fails - the entry would be absent, and
        provider_order_for would fall to the general list."""
        mapped = runner._map_tier4_pins("general:Together")
        assert mapped == (
            "general:Together,tier4_arm_a:,tier4_arm_d:")
        # The empty entry resolves to no providers, whatever the
        # general list carries - the routing layer's own
        # semantics, on the mapped line.
        with runner.tier4_pins(mapped):
            assert runner._arm_pin("A") == []
            assert runner._arm_pin("D") == []
            assert runner._arm_pin("D-pages") == []

    def test_the_mapping_is_idempotent(self):
        """A line the mapping already produced is re-mapped to
        itself - the dry run's own pin context composes with the
        run's.

        Break-proof: change the mapping to append without
        dropping its own previous entries, and the assert fails -
        the second mapping would carry the tier-4 entries
        twice."""
        raw = "tier3_arm_a:StreamLake,tier3_arm_d:Wafer"
        once = runner._map_tier4_pins(raw)
        assert runner._map_tier4_pins(once) == once

    def test_tier4_pins_installs_the_mapped_line_and_restores_it(
            self):
        """The pin context installs the mapped line on the
        harness settings for its duration - the line every
        single-call arm's chat reads - and restores the line it
        found afterwards.

        Break-proof: drop the `finally` block's restore, and the
        post-context assert fails - the settings would carry the
        mapped line after the context closed."""
        raw = "tier3_arm_a:StreamLake,tier3_arm_d:Wafer"
        previous = runner.harness_settings.openrouter_provider_order
        try:
            with runner.tier4_pins(raw):
                assert (runner.harness_settings
                        .openrouter_provider_order) == (
                    raw + ",tier4_arm_a:StreamLake,"
                    "tier4_arm_d:Wafer")
                assert runner._arm_pin("A") == ["StreamLake"]
                assert runner._arm_pin("D") == ["Wafer"]
            assert (runner.harness_settings
                    .openrouter_provider_order) == previous
        finally:
            runner.harness_settings.openrouter_provider_order = (
                previous)

    def test_the_arm_pin_keys_name_the_functions_the_arms_bill_to(
            self):
        """The pin key is the tier-4 function the arm's single
        call bills to - the key the client's accounting records
        the serving under, and the key the routing layer reads.
        D-pages is arm D's treatment, so it bills to arm D's
        function.

        Break-proof: change `_arm_pin_key` to key on the arm's
        own name, and the D-pages assert fails - the key would
        not name a function the call bills to."""
        assert runner._arm_pin_key("A") == "tier4_arm_a"
        assert runner._arm_pin_key("D") == "tier4_arm_d"
        assert runner._arm_pin_key("D-pages") == "tier4_arm_d"
        # The pin key is the function the arm executor bills to:
        # `_arm_single` bills `f"{function_prefix}_arm_{arm}"`
        # with arm D's own name for D-pages, and the client's
        # accounting records the serving under that function.
        assert runner._arm_pin_key("D-pages") == (
            f"tier4_arm_{runner.ceiling_key('D-pages').lower()}")

    def test_the_serving_mismatch_compares_the_provider_not_the_form(
            self):
        """The R7 comparison names the provider that served,
        on the provider's name - not on the string form each
        side writes it in. The live response names the
        provider bare ("InferenceNet"); the owner's order
        line writes the call-time specifier
        ("inference-net/fp4") - a form the repo measured
        2026-09-30 never matching the bare name raw
        (autornd/preflight.py, _base_provider). Measured
        live 2026-10-17: the batch-2 calibration's two
        D-pages units, both served by the pinned
        InferenceNet, were both flagged serving_mismatch on
        exactly that gap.

        Break-proof: revert the comparison to raw sets
        (set(served) <= set(pin)) and the first asserts
        fail - the live forms mismatch, and a correctly
        served unit would be thrown out of the readable
        counts as mis-served."""
        batch = PILOT
        servings = runner.DRY_RUN_SERVINGS
        catalogue = runner._dry_run_catalogue(servings)
        rates = _rates(catalogue)
        context = tier3._DryRunContext()
        questions = batch.questions()
        budget = runner.SweepBudget(
            cap=batch.calibration_ceiling)
        # The owner's real pin form on the dry run's line:
        # the D arm's entry is the call-time specifier the
        # owner ratified, not the dry run's serving id.
        pin_line = runner.DRY_RUN_PROVIDER_ORDER.replace(
            f"tier3_arm_d:{servings['D']}",
            "tier3_arm_d:inference-net/fp4")
        overrides = {
            "TIER3_ARM_A": servings["A"],
            "TIER3_ARM_B": servings["B"],
            "TIER3_ARM_C_1": servings["C"][0],
            "TIER3_ARM_C_2": servings["C"][1],
            "TIER3_ARM_D": servings["D"],
            "TIER3_SERVINGS_RATIFIED": (
                runner._servings_fingerprint(servings)),
            "TIER3_SPEND_AUTHORIZED": (
                f"{batch.calibration_ceiling:.2f}"),
        }
        def _unit_with_provider(provider):
            script = tier3.DryRunScript()
            script._calls[("T4-06", 1, "D-pages")] = [{
                "content": "an answer",
                "finish_reason": "stop",
                "provider": provider,
                "prompt_tokens": 900,
                "completion_tokens": 1200}]
            calls: list[dict[str, Any]] = []
            with runner._env_overrides(overrides), \
                    runner._harness_pin_overrides(
                        servings["E"]), \
                    runner.tier4_pins(pin_line):
                runner._install_rates(catalogue)
                factory = _recording_factory(
                    script, rates, context, calls)
                dispatcher = (
                    runner._dry_run_tool_dispatcher(
                        script, context))
                return asyncio.run(runner.run_tier4_unit(
                    ("T4-06", 1, "D-pages"), questions,
                    servings, budget, client_factory=factory,
                    tool_dispatcher=dispatcher,
                    batch=batch))
        # The live response's form: the bare provider name
        # the pinned order line's specifier names. Served by
        # the pinned provider - no mismatch.
        served = _unit_with_provider("InferenceNet")
        assert served.serving_pins == ["inference-net/fp4"]
        assert served.providers_by_tier == {
            "tier4_arm_d": ["InferenceNet"]}
        assert served.serving_mismatch is False
        # A provider outside the pin still mismatches - the
        # ruling's semantics, on the normalized name.
        mis_served = _unit_with_provider("Google AI Studio")
        assert mis_served.serving_mismatch is True


# ── (i) The batch registration (R9) ─────────────────────

class TestIBatchRegistration:
    """Every frozen batch registers itself in its manifest.json:
    the runner reads the figures from the manifest, and a
    manifest that does not register a field is not a frozen
    batch."""

    def test_load_batch_registers_every_figure(self):
        """Both frozen batches register themselves (R9): the
        candidates' sha256, each question's corpus sha256, the
        families, the calibration and pilot ceilings, the pilot's
        arms per family, the per-unit ceilings, the deadline and
        the single-call max_tokens.

        Break-proof: change `_read_batch` to read a figure from
        a module constant instead of the manifest, and the
        batch-2 assert fails - the constant would not carry the
        batch's own registration."""
        assert PILOT.name == "pilot"
        assert PILOT.families == {
            "T4-02": "F1", "T4-03": "F1", "T4-04": "F1",
            "T4-05": "F1", "T4-06": "F2"}
        assert PILOT.calibration_ceiling == 2.0
        assert PILOT.pilot_ceiling == 5.0
        assert PILOT.pilot_arms == {
            "F1": ("A", "D", "F", "E"),
            "F2": ("D-pages", "F", "E")}
        assert PILOT.per_unit_ceilings == {
            "A": 0.15, "D": 0.4, "D-pages": 0.4,
            "F": 0.4, "E": 1.5}
        assert PILOT.deadline_seconds == 3600
        assert PILOT.single_call_max_tokens == 32768
        assert BATCH2.name == "batch2"
        assert BATCH2.families == {"T4-15": "F2", "T4-16": "F2"}
        assert BATCH2.calibration_ceiling == 1.0
        assert BATCH2.pilot_ceiling == 5.0
        assert BATCH2.pilot_arms == {"F2": ("D-pages", "F", "E")}
        assert BATCH2.per_unit_ceilings == {
            "A": 0.15, "D": 0.4, "D-pages": 0.4,
            "F": 0.4, "E": 1.5}
        assert BATCH2.deadline_seconds == 3600
        assert BATCH2.single_call_max_tokens == 32768

    def test_the_manifests_sha256_conventions(self):
        """The manifest's two sha256 conventions, measured
        independently: the candidates' sha256 is the file's
        bytes, and a question's corpus sha256 is its pages'
        bytes concatenated in the manifest's listed order, no
        separator - ``cat <the listed pages> | sha256sum``.

        Break-proof: change `corpus_sha256` to hash the pages
        with a separator between them, and the independent
        measurement fails - the digest would not be the
        concatenation's."""
        assert PILOT.candidates_sha256 == hashlib.sha256(
            (runner.TIER4 / "pilot" / "candidates.json")
            .read_bytes()).hexdigest()
        digest = hashlib.sha256()
        for page in PILOT.corpus["T4-06"]:
            digest.update(page.read_bytes())
        assert PILOT.corpus_sha256["T4-06"] == digest.hexdigest()
        # Batch 2's two questions, each its own single page.
        for question_id in ("T4-15", "T4-16"):
            digest = hashlib.sha256()
            for page in BATCH2.corpus[question_id]:
                digest.update(page.read_bytes())
            assert BATCH2.corpus_sha256[question_id] == (
                digest.hexdigest())

    def test_a_manifest_missing_a_registered_field_refuses(
            self, tmp_path):
        """A manifest that does not register a field the runner
        needs is not a frozen batch - it refuses to load, naming
        the field (R9).

        Break-proof: change `registered` to default a missing
        field, and the assert fails - the batch would load on a
        figure it never registered."""
        _write_synthetic_batch(
            tmp_path / "holey", "holey",
            {"Q-1": "Q-1 page"}, missing="deadline_seconds")
        with pytest.raises(ValueError) as refused:
            runner.load_batch(tmp_path / "holey")
        assert "deadline_seconds" in str(refused.value)

class TestKSingleUseAuthorization:
    """R11 (the advisor's review of 2026-10-18): one authorisation
    pays for one run. Measured 2026-10-17: the pilot batch's
    calibration ran twice under one unchanged gate line, because the
    exact gate (R4) checks the amount, not whether it was spent."""

    def _env(self, tmp_path, amount="1.00"):
        env = tmp_path / ".env.tier3"
        env.write_text(f"TIER3_SPEND_AUTHORIZED={amount}\n",
                       encoding="utf-8")
        return env

    def test_a_second_run_under_one_authorisation_refuses(self, tmp_path):
        """The second claim names the run that spent the first.

        Break-proof: make `claim_authorization` return None
        unconditionally, and the second claim is not refused."""
        env = self._env(tmp_path)
        claims = tmp_path / "claims"
        first = runner.claim_authorization(
            claims, "pilot", "batch2", "5.00", env, tmp_path / "run-1.jsonl")
        second = runner.claim_authorization(
            claims, "pilot", "batch2", "5.00", env, tmp_path / "run-2.jsonl")
        assert first is None
        assert second is not None and "run-1.jsonl" in second

    def test_the_same_run_resuming_keeps_its_claim(self, tmp_path):
        """A resume writes to the same results file: it is the same
        run, so its own claim does not refuse it."""
        env = self._env(tmp_path)
        claims = tmp_path / "claims"
        path = tmp_path / "run-1.jsonl"
        assert runner.claim_authorization(
            claims, "pilot", "batch2", "5.00", env, path) is None
        assert runner.claim_authorization(
            claims, "pilot", "batch2", "5.00", env, path) is None

    def test_re_setting_the_line_authorises_another_run(self, tmp_path):
        """The owner re-authorises by re-setting the line; the new
        modification time keys a new claim."""
        import os as _os
        env = self._env(tmp_path)
        claims = tmp_path / "claims"
        assert runner.claim_authorization(
            claims, "pilot", "batch2", "5.00", env, tmp_path / "a.jsonl") is None
        stat = env.stat()
        _os.utime(env, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        assert runner.claim_authorization(
            claims, "pilot", "batch2", "5.00", env, tmp_path / "b.jsonl") is None

    def test_two_concurrent_launches_claim_exactly_once(self, tmp_path):
        """The claim is an exclusive create: of many simultaneous
        launchers, exactly one holds it.

        Break-proof: open the marker without O_EXCL, and more than
        one launcher claims."""
        import threading
        env = self._env(tmp_path)
        claims = tmp_path / "claims"
        barrier = threading.Barrier(8)
        results: list[str | None] = []
        lock = threading.Lock()

        def launch(i):
            barrier.wait()
            outcome = runner.claim_authorization(
                claims, "pilot", "batch2", "5.00", env, tmp_path / f"run-{i}.jsonl")
            with lock:
                results.append(outcome)

        threads = [threading.Thread(target=launch, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sum(1 for outcome in results if outcome is None) == 1

    def test_the_runner_refuses_a_second_paid_run_end_to_end(
            self, tmp_path, monkeypatch):
        """Through the real runner (mocked serving layer, a named
        claim directory): the second run of the calibration under
        the same authorisation refuses before its first call, naming
        the first run's records.

        Break-proof: delete the `if claim_dir is not None:` block in
        `_run_tier4_experiment`, and the second run executes."""
        monkeypatch.setattr(runner, "TIER3_ENV_FILE", self._env(tmp_path))
        claims = tmp_path / "claims"
        script = runner.build_calibration_dry_run_script(BATCH2)
        first = asyncio.run(runner._tier4_dry_run_mode(
            "calibration", script, batch=BATCH2, claim_dir=claims,
            results_path=tmp_path / "first.jsonl"))
        assert first["records"]
        with pytest.raises(runner.ExperimentRefused) as refused:
            asyncio.run(runner._tier4_dry_run_mode(
                "calibration", runner.build_calibration_dry_run_script(BATCH2),
                batch=BATCH2, claim_dir=claims,
                results_path=tmp_path / "second.jsonl"))
        assert "first.jsonl" in str(refused.value)
        assert refused.value.reason == "the authorisation was already spent"


class TestLArmFSequenceIsAReport:
    """R6 carried to tier 4 (2026-10-18): arm F's composed sequence
    worst case is reported, not refused, because the per-call guard
    binds. A single tier whose calls cannot fit still refuses."""

    def _rows(self, sequence_refuses, tier_refuses):
        return [
            {"tier": "engineering", "serving": "probe/eng", "worst_case": 0.1369,
             "tier_worst_case": 0.2739, "calls": 2, "refuses_even_at_zero_spend": tier_refuses},
            {"tier": "sequence", "serving": "verify-first bound", "worst_case": 0.7452,
             "tier_worst_case": None, "calls": 10, "refuses_even_at_zero_spend": sequence_refuses},
        ]

    def _preflight(self, monkeypatch, rows):
        monkeypatch.setattr(runner.tier3, "arm_f_worst_case", lambda *a, **k: rows)
        servings = runner.DRY_RUN_SERVINGS
        with runner.tier4_pins(runner.DRY_RUN_PROVIDER_ORDER):
            return runner.tier4_preflight(
                servings, runner._dry_run_catalogue(servings),
                credit=runner.DRY_RUN_CREDIT, ceiling=BATCH2.pilot_ceiling,
                arms=("F",), questions=BATCH2.questions(), mode="pilot", batch=BATCH2)

    def test_a_sequence_over_the_ceiling_is_reported_not_refused(self, monkeypatch):
        """Break-proof: drop `and row.get("tier") != "sequence"` from
        the arm-F refusal, and this test fails - the preflight
        refuses the pilot at zero spend, as it did on 2026-10-18."""
        report = self._preflight(monkeypatch, self._rows(True, False))
        assert not any(r.startswith("arm F/") for r in report.refusals), report.refusals
        assert any("arm F/sequence" in line and "reported, not refused" in line
                   for line in report.reports), report.reports

    def test_a_tier_whose_calls_cannot_fit_still_refuses(self, monkeypatch):
        report = self._preflight(monkeypatch, self._rows(False, True))
        assert any(r.startswith("arm F/engineering") for r in report.refusals), report.refusals
