"""The live phrasing the planner actually emitted, pinned against the classifier.

**What this is.** A characterisation fixture built from `ARCH-20260922-027`'s
committed trace. It pins what `_classify` does with the exact criterion the
planner produced on a live run — **including where that is wrong.**

**Read this before "fixing" a failure here.** `TestTheLiveWordingIsMisclassified`
asserts a KNOWN DEFECT (B17). It is not a description of desired behaviour. When
B17 is repaired those assertions SHOULD fail, and the right response is to update
them deliberately and say so — not to treat the failure as a regression. That is
convention 17 written into the file it applies to.

**Why a fixture and not another paid run.** The run cost $0.0434 and produced
this wording once. B16 regenerates criteria every run, so a second run measures a
different contract (convention 27) and could not reproduce this string on
purpose. The trace is the only stable copy, so the test reads it rather than
restating it — a hand-copied criterion would drift from the evidence it claims to
pin, which is convention 24's subject.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autornd.graph.checks import (
    FORM,
    PRESENCE,
    PROHIBITION,
    _classify,
    _forbidden_present,
    criteria_addressed,
)

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "docs" / "traces" / "b17-prohibition-branch.jsonl"

# Quoted from the objective in evals/scenarios/generalization/gen_house_style_prohibition.yaml,
# which took them from B17's row in HANDOVER.md — the criterion that opened the bug.
BANNED = ["leverage", "seamless", "robust", "in today's fast-paced world"]


@pytest.fixture(scope="module")
def unit():
    """The one unit record from the -027 run."""
    assert TRACE.is_file(), (
        f"{TRACE.relative_to(ROOT)} is missing — this fixture pins a live "
        f"measurement and cannot assert anything without it (convention 28)")
    lines = TRACE.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    units = [r for r in records if r.get("record") == "unit"]
    assert units, f"no unit record in {TRACE.name}; only {[r.get('record') for r in records]}"
    return units[0]


@pytest.fixture(scope="module")
def criteria(unit):
    got = unit["verdicts"]["plan"]["success_criteria"]
    assert got, "the trace carries no success criteria — nothing to classify"
    return got


@pytest.fixture(scope="module")
def draft(unit):
    text = unit["verdicts"]["implement"]["summary"]
    assert text.strip(), "the trace carries no implementation text"
    return text


@pytest.fixture(scope="module")
def banned_criterion(criteria):
    """The prohibition-shaped criterion, located by content rather than index."""
    matches = [c for c in criteria if all(b in c.lower() for b in BANNED)]
    assert len(matches) == 1, (
        f"expected exactly one criterion naming all four banned tokens, found "
        f"{len(matches)}. The trace's criteria are: {criteria}")
    return matches[0]


class TestTheDraftWasActuallyCompliant:
    """Everything below is only interesting if the work was genuinely correct."""

    def test_no_banned_token_appears_in_the_draft(self, draft):
        present = [b for b in BANNED if _forbidden_present(b, draft)]
        assert not present, f"the draft contains {present}; it is not a compliant exhibit"

    def test_the_draft_is_inside_the_required_word_count(self, draft):
        """Criterion 3 asked for 350-450 words. This is 401."""
        words = len(draft.split())
        assert 350 <= words <= 450, words


class TestTheLiveWordingIsMisclassified:
    """⚠️ PINS A KNOWN DEFECT (B17). These SHOULD fail when it is repaired."""

    def test_the_planner_wrote_contains_no_instances_of(self, banned_criterion):
        """The wording, verbatim, so the root cause is legible without the trace."""
        assert "contains no instances of" in banned_criterion.lower(), (
            f"the live criterion no longer carries the phrasing this fixture "
            f"exists to pin: {banned_criterion!r}")

    def test_it_is_classified_presence_not_prohibition(self, banned_criterion):
        """DEFECT. It is a negation over an explicit quoted token list.

        _PROHIBITION_MARKER knows avoid / banned / forbidden / prohibit /
        disallow / excludes / must not / may not / never uses / no use of.
        It does not know "contains no instances of", so no forbidden list is
        extracted, and the criterion falls through to the presence default.
        """
        shape, forbidden = _classify(banned_criterion)
        assert shape == PRESENCE, f"classification moved to {shape} — see this class's docstring"
        assert forbidden == [], f"tokens are now extracted: {forbidden}"

    def test_a_compliant_draft_therefore_scores_zero(self, banned_criterion, draft):
        """The consequence, and the reason the run died.

        Under presence, the criterion's only significant terms are the words it
        forbids — so satisfying it is what makes it fail.
        """
        result = criteria_addressed(criteria=[banned_criterion], text=draft)
        assert result.passed is False
        assert "0%" in result.detail, result.detail


class TestTheInversionItselfIsCorrect:
    """The ruled behaviour works. Only detection reaches it.

    This is the half that isolates the defect: give the SAME prohibition, over
    the SAME banned tokens, against the SAME draft, in wording the marker
    recognises, and the branch fires and passes the compliant draft.
    """

    # B17's original exhibit wording, from HANDOVER.md §4.2.
    RECOGNISED = ("avoids the banned words ('leverage', 'seamless', 'robust', "
                  "'in today's fast-paced world')")

    def test_the_recognised_wording_classifies_prohibition(self):
        shape, forbidden = _classify(self.RECOGNISED)
        assert shape == PROHIBITION, shape
        assert forbidden == BANNED, forbidden

    def test_and_passes_the_same_compliant_draft(self, draft):
        result = criteria_addressed(criteria=[self.RECOGNISED], text=draft)
        assert result.passed is True, result.detail

    def test_and_still_fails_a_draft_that_breaks_the_rule(self):
        """The fail direction, which the live scenario could not reach."""
        offending = "This robust platform helps teams move faster."
        result = criteria_addressed(criteria=[self.RECOGNISED], text=offending)
        assert result.passed is False, result.detail

    def test_the_two_wordings_are_the_same_prohibition(self, banned_criterion):
        """Both name all four tokens; only the verb phrase differs.

        Stated as an assertion rather than a comment, because it is the whole
        finding: what separated a working branch from a dead run was phrasing,
        and B16 rewrites that phrasing every run.
        """
        for token in BANNED:
            assert token in banned_criterion.lower()
            assert token in self.RECOGNISED.lower()
        assert _classify(banned_criterion)[0] != _classify(self.RECOGNISED)[0]


class TestWhyTheDoubtDirectionWasNotFlipped:
    """Evidence for ARCH-20260922-029's refusal to apply B17-R2 as written.

    B17-R2 says: on doubt, abstain; never default to presence. There is no
    doubt state in _classify — it is deterministic, and every criterion that
    matches no positive pattern falls through to presence. So "never default to
    presence" can only be implemented by making the fallthrough abstain, and
    this test records what that would do to the live plan.
    """

    def test_no_criterion_in_the_live_plan_matched_any_positive_pattern(self, criteria):
        """All six fell through to the default — so the default IS the check."""
        shapes = [_classify(c)[0] for c in criteria]
        assert shapes == [PRESENCE] * len(criteria), shapes
        assert FORM not in shapes and PROHIBITION not in shapes

    def test_flipping_the_fallthrough_would_make_coverage_pass_unconditionally(
        self, criteria, draft, monkeypatch
    ):
        """Every criterion abstains, nothing is measured, and the gate opens.

        Coverage is the judge that dissented on all six iterations of the live
        run. A version of it that abstains on everything stops dissenting, and
        work ships unchecked — which is a change to what the harness concludes,
        not a repair to how reliably it concludes it.
        """
        import autornd.graph.checks as checks

        real = checks._classify
        monkeypatch.setattr(
            checks, "_classify",
            lambda c: (FORM, []) if real(c)[0] == PRESENCE else real(c))

        result = checks.criteria_addressed(criteria=criteria, text=draft)
        assert result.passed is True, (
            "expected the flipped fallthrough to pass everything; if this no "
            "longer holds, the evidence for refusing B17-R2 has changed and the "
            "refusal should be revisited")
        assert "abstained" in result.detail, result.detail
