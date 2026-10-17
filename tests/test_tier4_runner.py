"""The tier-4 pilot tooling's tests (command ARCH-20261017-122's
acceptance criteria (a)-(g)).

Every test runs the real runner (evals/tier4/runner.py, imported
by path the way the tier-3 tests import it) against the frozen
pilot batch (evals/tier4/pilot/, read-only). The mocked dry run
is the instrument's own: scripted clients that bill through the
real guard and accounting, a fixture catalogue, and a stand-in at
the pipeline boundary for arms E and F. Nothing reaches the
network: the suite's guard (tests/conftest.py) refuses every
non-loopback socket, so the dry run's "no network" is proved by
the guard itself, not asserted here.

Each test is proved by breaking one line of the runner and
quoting the failure - the break-proof is recorded under the test
it proves. A test that cannot fail proves nothing (convention 22).

The eight criteria, as the command orders them:
(a) the leakage guard - every unit of both modes carries only the
    given texts, with its break-proof;
(b) profile isolation - an F2 unit of F/E grounds with all three
    pages, an F1 unit with none, with its break-proof;
(c) the freeze guard - a one-byte change to candidates.json, a
    corpus page or a docs/tier4 copy refuses, naming the file;
(d) the plan - the calibration's nine units, the pilot's
    refusals;
(e) the gate and the preflight - R4's exact-equality gate both
    ways, the credit preflight, the printed worst cases;
(f) the mocked dry run of both modes - zero spend, every record
    field, the arm-blind reading sheet, every failure class;
(g) tier 3 unchanged - the scenario dispatch that the tier-4
    scenario ids generalize still keys the tier-3 dry run's own
    ids to the same workflows.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
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

QUESTIONS = runner.candidate_index()
PAGES = [content for _name, content in runner.corpus_pages()]
PAGE_NAMES = [name for name, _content in runner.corpus_pages()]

# The two modes' plans, as the runner builds them.
CALIBRATION = runner.calibration_plan()
PILOT, _PILOT_REFUSALS = runner.pilot_plan(
    ["T4-02", "T4-03", "T4-04", "T4-06"])


def _arms_by_family(mode: str) -> dict[str, tuple[str, ...]]:
    if mode == "calibration":
        return {"F1": runner.CALIBRATION_ARMS_F1,
                "F2": runner.CALIBRATION_ARMS_F2}
    return {"F1": runner.PILOT_ARMS_F1,
            "F2": runner.PILOT_ARMS_F2}


def _every_unit(mode: str) -> list[tuple[str, str]]:
    """Every (question id, arm) pair the mode's plan runs."""
    return [(unit[0], unit[2])
            for unit in (CALIBRATION if mode == "calibration"
                         else PILOT)]


def _dry_run() -> dict[str, Any]:
    """The mocked dry run of both modes, once per session."""
    cached = getattr(_dry_run, "_result", None)
    if cached is None:
        cached = asyncio.run(runner.tier4_dry_run())
        _dry_run._result = cached
    return cached


# ── (a) The leakage guard ──────────────────────────────

class TestALeakageGuard:
    """The model-visible text is the candidate's request only,
    plus, for arm D on F2, the corpus pages. Never the
    requirements, the reference design, the worked solution, the
    wrong designs or the difficulty rationale."""

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
                    arm, candidate)
                given = PAGES if arm == "D-pages" else ()
                findings = runner.leakage_findings(
                    message, candidate, given=given)
                assert not findings, (mode, question_id, arm,
                                       findings[:2])

    def test_the_d_pages_message_is_the_registered_composition(
            self):
        """Arm D's F2 user message is the request, the registered
        separator, and the three corpus pages verbatim and in name
        order, each preceded by its file name - and the unit
        record's message sha256 is that message's.

        Break-proof: change `PAGES_SEPARATOR` to a different
        string, and the composition assert fails; change
        `corpus_pages` to sort by content, and the name-order
        assert fails."""
        candidate = QUESTIONS["T4-06"]
        expected = candidate["request"] + runner.PAGES_SEPARATOR + (
            "\n\n".join(
                f"{name}\n\n{content}"
                for name, content in runner.corpus_pages()))
        message = runner.d_pages_message(candidate)
        assert message == expected
        assert len(PAGE_NAMES) == 3
        assert PAGE_NAMES == sorted(PAGE_NAMES)
        # The record's field is the composed message's own sha256.
        record = [
            record for record in _dry_run()["calibration"]["records"]
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
                leaked = (runner.model_visible_message(arm, candidate)
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
        leaked = (runner.d_pages_message(f2) + "\n\n"
                  + f2["worked_solution"])
        assert runner.leakage_findings(leaked, f2, given=PAGES)


# ── (b) Profile isolation ──────────────────────────────

class TestBProfileIsolation:
    """F2 units of arms F and E run under the tier-4 corpus
    profile; F1 units of every arm run without it, so no corpus
    text reaches an F1 question."""

    def test_an_f2_unit_of_f_and_e_grounds_with_all_three_pages(
            self):
        """The tier-4 profile's grounding context is the three
        corpus pages, exactly as load_docs_context loads them.

        Break-proof: change `profiles/tier4.yaml`'s name to
        another value, and the context loads nothing - the
        manifest's directory is the profile's name, lowercased."""
        context = runner.corpus_context()
        for name, content in runner.corpus_pages():
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

        Break-proof: change `unit_profile` to return
        `TIER4_PROFILE` for every unit, and the F1 records of the
        dry run would carry profile 'tier4' - the dry run's
        profile test below fails."""
        with runner._profile_selected(runner.TIER4_PROFILE):
            context = runner.load_docs_context([], [])
        assert runner.corpus_pages()[0][1] in context

    def test_the_units_run_under_their_registered_profile(
            self):
        """`unit_profile` names the tier-4 profile for an F2 unit
        of F or E and the default for every other unit - D-pages
        carries the pages in its message, so it runs the
        single-call treatment under the default.

        Break-proof: change `unit_profile`'s condition to
        `family == 'F2'` alone, and the D-pages assert fails."""
        assert runner.unit_profile("F2", "E") == "tier4"
        assert runner.unit_profile("F2", "F") == "tier4"
        assert runner.unit_profile("F2", "D-pages") is None
        assert runner.unit_profile("F1", "A") is None
        assert runner.unit_profile("F1", "D") is None
        assert runner.unit_profile("F1", "E") is None
        assert runner.unit_profile("F1", "F") is None

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
        for mode in ("calibration", "pilot"):
            for record in _dry_run()[mode]["records"]:
                wanted = ("tier4"
                          if record["family"] == "F2"
                          and record["arm"] in ("E", "F")
                          else "default")
                assert record["profile"] == wanted, (
                    mode, record["question_id"], record["arm"],
                    record["profile"], wanted)


# ── (c) The freeze guard ───────────────────────────────

class TestCFreezeGuard:
    """Both modes refuse to start unless candidates.json and the
    corpus hash to the evidence's sha256 values, and docs/tier4/
    pages are byte-identical to evals/tier4/pilot/corpus/."""

    @pytest.fixture
    def frozen_copies(self):
        """A tmp copy of the frozen batch, the corpus and the
        docs/tier4 copies, with the runner's path constants
        rebound to them for the duration."""
        tmp = Path(tempfile.mkdtemp())
        pilot = tmp / "pilot"
        shutil.copytree(runner.PILOT_DIR, pilot)
        docs = tmp / "docs" / "tier4"
        docs.parent.mkdir(parents=True)
        shutil.copytree(runner.DOCS_TIER4, docs)
        saved = (runner.BATCH_PATH, runner.CORPUS_DIR,
                 runner.DOCS_TIER4)
        runner.BATCH_PATH = pilot / "candidates.json"
        runner.CORPUS_DIR = pilot / "corpus"
        runner.DOCS_TIER4 = docs
        try:
            yield pilot, pilot / "corpus", docs
        finally:
            runner.BATCH_PATH, runner.CORPUS_DIR, \
                runner.DOCS_TIER4 = saved
            shutil.rmtree(tmp)

    @staticmethod
    def _flip(path: Path) -> None:
        """A one-byte change: the first byte, flipped."""
        data = bytearray(path.read_bytes())
        data[0] = data[0] ^ 0x01
        path.write_bytes(bytes(data))

    def test_the_guard_holds_on_the_frozen_tree(self):
        """The tree as it stands: no refusals, and the measured
        hashes are the evidence's registered values.

        Break-proof: change `REGISTERED_BATCH_SHA256` by one
        hex digit, and the assert fails - the measured hash no
        longer equals the registered one."""
        assert runner.check_freeze() == []
        assert runner.batch_sha256() == runner.REGISTERED_BATCH_SHA256
        assert runner.corpus_sha256() == runner.REGISTERED_CORPUS_SHA256

    def test_a_one_byte_change_to_candidates_json_refuses(
            self, frozen_copies):
        """Break-proof: change `check_freeze` to compare only the
        corpus, and this test fails with no refusal for the
        mutated batch file."""
        pilot, _corpus, _docs = frozen_copies
        self._flip(pilot / "candidates.json")
        refusals = runner.check_freeze()
        assert refusals
        assert any("candidates.json" in refusal
                    for refusal in refusals), refusals

    def test_a_one_byte_change_to_a_corpus_page_refuses(
            self, frozen_copies):
        """Break-proof: change `check_freeze` to skip the corpus
        hash, and this test fails - the docs-copy comparison still
        fires, but the corpus's own hash refusal is gone."""
        _pilot, corpus, _docs = frozen_copies
        self._flip(corpus / "T4-06-vortexia-1.md")
        refusals = runner.check_freeze()
        assert refusals
        assert any("corpus" in refusal for refusal in refusals)
        assert any("T4-06-vortexia-1.md" in refusal
                    for refusal in refusals), refusals

    def test_a_one_byte_change_to_a_docs_copy_refuses(
            self, frozen_copies):
        """Break-proof: change `check_freeze` to compare the docs
        copies by name only, and this test fails with no
        refusal."""
        _pilot, _corpus, docs = frozen_copies
        self._flip(docs / "T4-06-vortexia-2.md")
        refusals = runner.check_freeze()
        assert refusals
        assert any("T4-06-vortexia-2.md" in refusal
                    for refusal in refusals), refusals

    def test_a_deleted_docs_copy_refuses(self, frozen_copies):
        """Break-proof: change `check_freeze` to test only
        `docs_copy.exists()`, and a truncated copy would pass -
        the byte comparison is the guard."""
        _pilot, _corpus, docs = frozen_copies
        (docs / "T4-06-vortexia-3.md").unlink()
        refusals = runner.check_freeze()
        assert refusals
        assert any("T4-06-vortexia-3.md" in refusal
                    for refusal in refusals), refusals

    def test_both_modes_refuse_to_start_when_the_guard_fails(
            self, frozen_copies):
        """The refusal is the modes' own: `run_tier4_experiment`
        raises `ExperimentRefused` naming the drifted file, before
        any gate or network call.

        Break-proof: move the freeze check after the gate check in
        `run_tier4_experiment`, and this test fails - the gate's
        refusal, not the freeze's, is raised first."""
        pilot, _corpus, _docs = frozen_copies
        self._flip(pilot / "candidates.json")
        with pytest.raises(runner.ExperimentRefused) as refused:
            asyncio.run(runner.run_tier4_experiment(
                "calibration",
                client_factory=_no_client_factory(),
                catalogue=runner._dry_run_catalogue(
                    runner.DRY_RUN_SERVINGS),
                credit=runner.DRY_RUN_CREDIT))
        assert any("candidates.json" in refusal
                    for refusal in refused.value.detail), (
            refused.value.detail)


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
    """The calibration plans exactly nine units; the pilot plans
    the named ids x their family's arms and refuses what it
    cannot run."""

    def test_the_calibration_plans_exactly_nine_units(self):
        """A on T4-02..T4-05, D on T4-02..T4-05, D-pages on
        T4-06, one repetition each - and the seeded interleaved
        order is the one an independent reconstruction of the
        enumeration and the registered seed produces (the guard
        test's own discipline).

        Break-proof: change `CALIBRATION_SEED`, and the digest
        assert fails; change the enumeration to `for arm ... for
        question ...`, and the order's digest fails."""
        assert len(CALIBRATION) == 9
        assert sorted((unit[0], unit[2]) for unit in CALIBRATION) == (
            sorted(
                [(question_id, arm)
                 for question_id in runner.F1_QUESTION_IDS
                 for arm in runner.CALIBRATION_ARMS_F1]
                + [("T4-06", "D-pages")]))
        # The independent reconstruction: the same enumeration and
        # the same seed, built here from the registered constants.
        units = [[question_id, 1, arm]
                 for question_id in runner.F1_QUESTION_IDS
                 for arm in runner.CALIBRATION_ARMS_F1]
        units += [["T4-06", 1, arm]
                  for arm in runner.CALIBRATION_ARMS_F2]
        import random
        random.Random(runner.CALIBRATION_SEED).shuffle(units)
        assert CALIBRATION == units
        assert runner._order_digest(CALIBRATION) == (
            runner._order_digest(units))

    def test_the_pilot_plans_the_named_ids_x_their_family_arms(
            self):
        """Four named ids - two F1, one F1, one F2 - x their
        family's arms: 4 + 4 + 4 + 3 = 15 units, in the seeded
        interleaved order, reconstructed independently.

        Break-proof: change `PILOT_SEED`, and the digest assert
        fails; change the family arm sets, and the unit-count
        assert fails."""
        assert len(PILOT) == 15
        counts: dict[str, int] = {}
        for unit in PILOT:
            counts[unit[2]] = counts.get(unit[2], 0) + 1
        assert counts == {"A": 3, "D": 3, "D-pages": 1, "E": 4,
                          "F": 4}
        units: list[list[Any]] = []
        for question_id in ("T4-02", "T4-03", "T4-04", "T4-06"):
            family = QUESTIONS[question_id]["family"]
            for arm in runner.family_arms(family, "pilot"):
                units.append([question_id, 1, arm])
        import random
        random.Random(runner.PILOT_SEED).shuffle(units)
        assert PILOT == units

    def test_the_pilot_refuses_more_than_the_registered_limit(
            self):
        """Break-proof: change `PILOT_ID_LIMIT` to 5, and the
        refusal disappears - the limit is the registered constant,
        not a count the plan happens to produce."""
        order, refusals = runner.pilot_plan(
            ["T4-02", "T4-03", "T4-04", "T4-05", "T4-06"])
        assert order == []
        assert any("limit" in refusal for refusal in refusals)

    def test_the_pilot_refuses_an_id_outside_the_batch(self):
        """Break-proof: change `pilot_plan` to skip unknown ids
        instead of refusing, and the refusal disappears and the
        plan runs four units - the frozen batch is the plan's
        population."""
        order, refusals = runner.pilot_plan(["T4-02", "T4-99"])
        assert order == []
        assert any("not in the frozen batch" in refusal
                    for refusal in refusals), refusals

    def test_the_pilot_refuses_an_f2_id_with_arm_a(self):
        """Arm A does not run on F2 (the command's constraint):
        an explicit arm restriction naming it is refused, not
        silently skipped.

        Break-proof: change `pilot_plan` to `continue` past an
        arm the family does not run, and the refusal disappears -
        the unit would be dropped silently, a plan the owner
        never saw."""
        order, refusals = runner.pilot_plan(["T4-06"], arms=("A",))
        assert order == []
        assert any("arm A does not run" in refusal
                    for refusal in refusals), refusals

    def test_the_pilot_refuses_a_repeated_id(self):
        """Break-proof: remove the repetition check, and the plan
        runs the id's arms twice - a repetition the owner did not
        name."""
        order, refusals = runner.pilot_plan(["T4-02", "T4-02"])
        assert order == []
        assert any("twice" in refusal for refusal in refusals)


# ── (e) The gate and the preflight ─────────────────────

class TestEGateAndPreflight:
    """The gate is R4's: TIER3_SPEND_AUTHORIZED equals the mode's
    registered ceiling exactly. The preflight prints each arm's
    per-call and per-unit worst case, and the credit preflight
    refuses below the mode's ceiling."""

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
        """R4 both ways: the calibration's gate clears at $2.00
        and refuses at $5.00, naming the ceiling; the pilot's
        gate clears at $5.00 and refuses at $2.00.

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
            runner.CALIBRATION_CEILING, "calibration") == []
        assert runner.tier4_gate_report(
            pilot, servings, fingerprint,
            runner.PILOT_CEILING, "pilot") == []
        for authorized in ("5.00", None, "abc"):
            missing = runner.tier4_gate_report(
                self._settings(authorized, fingerprint),
                servings, fingerprint,
                runner.CALIBRATION_CEILING, "calibration")
            assert missing, authorized
            assert any("TIER3_SPEND_AUTHORIZED" in refusal
                        for refusal in missing), missing
        for authorized in ("2.00", "5.01", None):
            missing = runner.tier4_gate_report(
                self._settings(authorized, fingerprint),
                servings, fingerprint,
                runner.PILOT_CEILING, "pilot")
            assert missing, authorized
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
            runner.CALIBRATION_CEILING, "calibration")
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
        for mode, ceiling in (("calibration", runner.CALIBRATION_CEILING),
                              ("pilot", runner.PILOT_CEILING)):
            below = runner.tier4_preflight(
                servings, catalogue, credit=ceiling - 0.01,
                ceiling=ceiling, arms=runner.mode_arms(mode),
                questions=QUESTIONS)
            assert any("remaining credit" in refusal
                        for refusal in below.refusals), below.refusals
            at = runner.tier4_preflight(
                servings, catalogue, credit=ceiling,
                ceiling=ceiling, arms=runner.mode_arms(mode),
                questions=QUESTIONS)
            assert not any("remaining credit" in refusal
                            for refusal in at.refusals), at.refusals
            unreadable = runner.tier4_preflight(
                servings, catalogue, credit=None,
                ceiling=ceiling, arms=runner.mode_arms(mode),
                questions=QUESTIONS)
            assert any("could not be read" in refusal
                        for refusal in unreadable.refusals), (
                unreadable.refusals)

    def test_the_preflight_prints_each_arms_worst_case(self):
        """Every arm the pilot runs - A, D, D-pages, F, E - has
        its per-call and per-unit worst case in the preflight's
        reports, at the fixture catalogue's shape: the single-call
        arms' one call, arm F's per-tier calls and its sequence,
        arm E's per-tier calls.

        Break-proof: change `tier4_preflight` to append the E and
        F rows as refusals only (dropping the report lines), and
        the arm E and arm F asserts fail - the preflight would
        refuse without printing the figures the command orders it
        to print."""
        servings = runner.DRY_RUN_SERVINGS
        catalogue = runner._dry_run_catalogue(servings)
        report = runner.tier4_preflight(
            servings, catalogue, credit=runner.DRY_RUN_CREDIT,
            ceiling=runner.PILOT_CEILING,
            arms=runner.mode_arms("pilot"), questions=QUESTIONS)
        assert report.refusals == []
        printed = "\n".join(report.reports)
        for arm in ("A", "D", "D-pages"):
            assert f"arm {arm}: one call" in printed, printed
            assert f"${runner.TIER4_CEILINGS[runner.ceiling_key(arm)]:.2f}" \
                in printed
        for tier in ("triage", "research", "search",
                     "engineering", "judge"):
            assert f"arm F/{tier}:" in printed, printed
            assert f"arm E/{tier}:" in printed, printed
        # The per-call and per-unit figures are stated, not
        # implied: every report line carries a worst case and a
        # ceiling.
        for line in report.reports:
            assert "worst case" in line, line
            assert "ceiling" in line, line


# ── (f) The mocked dry run ─────────────────────────────

class TestFDryRun:
    """The mocked dry run of both modes: zero spend, every record
    field, the arm-blind reading sheet, and every failure class
    the command names, at least once per mode."""

    def test_both_modes_run_at_zero_spend(self):
        """The dry run's total spend stays inside each mode's
        registered ceiling - the scripted clients bill through the
        real guard and accounting, so the figures are the real
        arithmetic at the fixture rates, and no network call
        happens (the suite's guard refuses every non-loopback
        socket).

        Break-proof: change `DRY_RUN_CREDIT` to a figure below a
        mode's ceiling, and the dry run refuses to start - the
        credit preflight is the real one."""
        for mode in ("calibration", "pilot"):
            result = _dry_run()[mode]
            ceiling = (runner.CALIBRATION_CEILING if mode == "calibration"
                       else runner.PILOT_CEILING)
            assert result["budget"]["spent"] <= ceiling, (
                mode, result["budget"])
            assert result["budget"]["cap"] == ceiling
            # Every unit the plan names is a record: nothing ran
            # twice and nothing was dropped.
            assert len(result["records"]) == result["order_units"]

    def test_the_header_carries_the_registered_figures(self):
        """The results header carries the batch sha256, the corpus
        sha256, the mode, the order digest and the servings
        fingerprint - the five figures the command's RECORDS
        constraint names, and the ceilings and deadline beside
        them.

        Break-proof: drop `corpus_sha256` from the log's config,
        and the header assert fails."""
        for mode in ("calibration", "pilot"):
            path = Path(_dry_run()[mode]["path"])
            header = json.loads(
                path.read_text(encoding="utf-8").splitlines()[0])
            assert header["record"] == "header"
            assert header["mode"] == mode
            assert header["batch_sha256"] == runner.batch_sha256()
            assert header["corpus_sha256"] == runner.corpus_sha256()
            assert header["servings_fingerprint"] == (
                runner._servings_fingerprint(runner.DRY_RUN_SERVINGS))
            assert header["authorization_ceiling"] == (
                runner.CALIBRATION_CEILING if mode == "calibration"
                else runner.PILOT_CEILING)
            assert header["ceilings"] == runner.TIER4_CEILINGS
            assert header["deadline_seconds"] == (
                runner.TIER4_DEADLINE_SECONDS)
            assert header["order_units"] == _dry_run()[mode][
                "order_units"]
            assert header["order_sha256"] == _dry_run()[mode][
                "order_sha256"]

    def test_the_records_carry_every_field(self):
        """Every unit record carries the command's RECORDS fields:
        question id, family, arm, profile, the exact user message's
        sha256, and the tier-3 unit record fields (status, answer,
        candidate, iterations, reason, stop_reason, calls, cost,
        seconds).

        Break-proof: drop `message_sha256` from
        `tier4_unit_record`, and the assert fails; drop the
        pipeline record's surfacing of `candidate`, and that
        assert fails."""
        fields = ("question_id", "repetition", "family", "arm",
                  "profile", "message_sha256", "status", "answer",
                  "candidate", "iterations", "reason", "stop_reason",
                  "calls", "cost", "seconds", "serving", "delivered")
        for mode in ("calibration", "pilot"):
            for record in _dry_run()[mode]["records"]:
                for field in fields:
                    assert field in record, (mode, field)
        # The D-pages record's message sha256 is the composed
        # message's own, and the F2 records of F and E name the
        # tier-4 profile.
        calibration = _dry_run()["calibration"]["records"]
        d_pages = [record for record in calibration
                    if record["arm"] == "D-pages"]
        assert d_pages
        for record in d_pages:
            assert record["message_sha256"] == runner.message_sha256(
                "D-pages", QUESTIONS["T4-06"])

    def test_the_reading_sheet_is_generated_and_arm_blind(self):
        """One entry per answered unit, in a seeded order, with no
        arm label: each entry carries the question's id, family,
        request and requirement statements - everything a reading
        needs - and the delivered answer.

        Break-proof: add the arm to the sheet's entries, and the
        arm-blind assert fails; drop the requirement statements,
        and the statements assert fails."""
        for mode in ("calibration", "pilot"):
            result = _dry_run()[mode]
            sheet = _dry_run()["reading_sheets"][mode]
            answered = [record for record in result["records"]
                        if record.get("answer")]
            assert sheet["units"] == len(answered)
            assert sheet["mode"] == mode
            assert len(sheet["entries"]) == len(answered)
            for entry in sheet["entries"]:
                assert "arm" not in entry, entry
                candidate = QUESTIONS[entry["question_id"]]
                assert entry["family"] == candidate["family"]
                assert entry["request"] == candidate["request"]
                assert [item["statement"]
                        for item in entry["requirement_statements"]
                        ] == [requirement["statement"]
                              for requirement
                              in candidate["requirements"]]
                assert entry["answer"] in {
                    record["answer"] for record in answered}
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
        for mode in ("calibration", "pilot"):
            result = _dry_run()[mode]
            census = result["census"]
            assert census.get("refusal", 0) >= 1, census
            assert census.get("deadline", 0) >= 1, census
            assert census.get("budget_stop", 0) >= 1, census
            provider_failures = [
                record for record in result["records"]
                if record["status"] == "incomplete"
                and str(record.get("stop_reason", "")).startswith(
                    "ProviderFailure")]
            assert provider_failures, (mode, census)
        # The exhibits are where the command's dry run puts them:
        # the calibration's budget stop is one call booking just
        # under the $2.00 authorization, refused by the unit's own
        # $0.30 ceiling after the call.
        calibration = _dry_run()["calibration"]["records"]
        booked = [record for record in calibration
                  if record["arm"] == "D"
                  and record["status"] == "incomplete"
                  and record["cost"] > runner.TIER4_CEILINGS["D"]]
        assert booked, calibration
        assert booked[0]["cost"] < runner.CALIBRATION_CEILING
        # The pilot's budget stop is composed: the ceiling-tail
        # defaults exhaust the $5.00 authorization inside the plan,
        # so the units after the crossing skip through the fit rule.
        pilot = _dry_run()["pilot"]
        assert pilot["census"]["budget_stop"] >= 1
        skipped = [record for record in pilot["records"]
                    if record["status"] == "skipped"]
        assert all("budget" in str(record.get("stop_reason", ""))
                    for record in skipped), skipped

    def test_the_dry_run_is_resumable(self):
        """A second invocation of a mode re-reads its own records
        and runs nothing twice: the log's resume is the tier-3
        discipline, on the tier-4 plan.

        Break-proof: delete the `if key in recorded: continue`
        line from `run_tier4_experiment`, and the second run's
        file carries every unit twice - the unit count doubles."""
        result = asyncio.run(runner._tier4_dry_run_mode(
            "calibration", runner.build_calibration_dry_run_script()))
        assert len(result["records"]) == result["order_units"]
        path = Path(result["path"])
        lines = [line for line in
                 path.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
        unit_lines = [line for line in lines
                      if json.loads(line).get("record") == "unit"]
        assert len(unit_lines) == result["order_units"]


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
