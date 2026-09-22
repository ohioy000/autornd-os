"""The prohibition scenario is registered, discoverable, and still says what it was registered to say.

**Why this exists.** `gen_house_style_prohibition` is an *input*, built by
`ARCH-20260922-026` to reach one branch of the coverage check that two paid runs
never exercised. An input that silently stops carrying its banned word list is
worse than a missing one: the run still costs money, still produces a trace, and
the trace answers a different question than the one registered.

**What it checks, and why each part.** Convention 22 says an instrument's test
simulates the condition it watches end to end, so this loads the scenario the way
the harness loads it — `load_scenarios()` on the *directory*, not `parse()` on the
file — because the failure mode that matters is "the harness cannot see it", and
a file can parse perfectly while sitting where nothing globs it.

Convention 28 says a guard asserts it computed its subject first. So the directory
load is asserted non-empty before anything is concluded from it: an empty glob
would otherwise make every "no bad scenario found" assertion below vacuously true.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autornd.evals.scenario import load_scenarios

ROOT = Path(__file__).resolve().parents[1]
GENERALIZATION = ROOT / "evals" / "scenarios" / "generalization"
SCENARIO_ID = "gen_house_style_prohibition"
REGISTRATION = ROOT / "docs" / "preregistration-b17-prohibition-branch.md"

# The list is quoted from B17's row in HANDOVER.md §4.2 — the criterion that
# opened the bug. If the scenario stops naming all four, it is no longer the
# input that was registered, whatever its filename says.
BANNED = ["leverage", "seamless", "robust", "in today's fast-paced world"]


@pytest.fixture(scope="module")
def discovered():
    """Every scenario the harness finds in the generalization directory."""
    scenarios = load_scenarios(GENERALIZATION)
    assert scenarios, (
        "load_scenarios found nothing in evals/scenarios/generalization — every "
        "assertion below would pass vacuously on an empty set (convention 28)")
    return scenarios


class TestTheHarnessCanSeeIt:
    def test_the_directory_load_finds_it(self, discovered):
        """Discoverability, not parseability. A file the glob misses is invisible."""
        found = [s.id for s in discovered]
        assert SCENARIO_ID in found, (
            f"{SCENARIO_ID} is not discoverable by load_scenarios; the harness "
            f"globs '*.yaml' non-recursively, so a scenario in a subdirectory or "
            f"with another extension does not exist as far as a run is concerned. "
            f"Found: {found}")

    def test_its_id_is_unique_in_the_directory(self, discovered):
        """load_scenarios raises on a duplicate, so this pins the intent too."""
        ids = [s.id for s in discovered]
        assert ids.count(SCENARIO_ID) == 1, f"duplicate id in {ids}"


class TestItStillSaysWhatItWasRegisteredToSay:
    @pytest.fixture
    def scenario(self, discovered):
        return next(s for s in discovered if s.id == SCENARIO_ID)

    @pytest.mark.parametrize("word", BANNED)
    def test_the_request_names_every_banned_word(self, scenario, word):
        """The whole point of the objective is that it names the prohibition.

        If the planner is to emit a prohibition-shaped criterion, the objective
        has to give it one to restate. A request that has lost a word from the
        list is a different experiment.
        """
        assert word in scenario.request.lower(), (
            f"the objective no longer names {word!r} — this scenario exists to "
            f"put that exact list in front of the planner")

    def test_the_request_states_the_prohibition_as_hard(self, scenario):
        """A preference does not reliably become a criterion; a constraint does."""
        text = scenario.request.lower()
        assert "must not contain" in text, (
            "the objective no longer states the ban as a hard constraint on the "
            "finished text")

    def test_it_is_tagged_for_the_bug_it_serves(self, scenario):
        assert "b17" in [t.lower() for t in scenario.tags], (
            f"tags are how this is selected for the -027 run; got {scenario.tags}")

    def test_it_asserts_coverage_passes(self, scenario):
        """Registered prediction (c), stated where the harness will score it."""
        assert scenario.expect.get("criteria_addressed") is True, (
            "criteria_addressed is registered prediction (c) — on a compliant "
            "draft the prohibition branch passes coverage. Removing it makes the "
            "run unable to score the thing it is bought to test")


class TestTheRegistrationPrecedesTheRun:
    """A pre-registration that lost its predictions is not a pre-registration."""

    @pytest.fixture
    def text(self):
        assert REGISTRATION.is_file(), f"{REGISTRATION.name} is missing"
        body = REGISTRATION.read_text(encoding="utf-8")
        assert body.strip(), "the registration is empty"
        return body

    @pytest.mark.parametrize("marker", ["**(a)", "**(b)", "**(c)", "**(d)"])
    def test_all_four_predictions_are_numbered_and_present(self, text, marker):
        assert marker in text, (
            f"registered prediction {marker} is gone — predictions are not "
            f"added, dropped or reworded after a result is seen")

    def test_the_engineered_disclosure_is_in_the_first_paragraph(self, text):
        """ARCH-20260922-026 requires this, and requires it FIRST.

        A passing result must not be read as evidence that a content corpus
        naturally produces prohibition criteria. Burying that below the
        predictions would let the two be confused, which the command forbids.
        """
        first = text.split("\n\n")[1] if "\n\n" in text else text
        assert "engineered to reach the branch" in first.lower(), (
            "the first paragraph no longer discloses that the scenario is "
            "engineered to reach the branch")

    def test_prediction_d_is_declared_unreachable_not_promised(self, text):
        assert "NOT REACHABLE BY" in text, (
            "prediction (d) must stay declared unreachable by this scenario — "
            "the command says to say so now rather than promise it")
