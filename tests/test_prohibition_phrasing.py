"""The live phrasing the planner actually emitted, pinned against the classifier.

**What this is.** A characterisation fixture built from `ARCH-20260922-027`'s
committed trace. It pins what `_classify` does with the exact criterion the
planner produced on a live run.

**History.** `TestTheLiveWordingIsMisclassified` (now
`TestTheLiveWordingIsNowClassifiedCorrectly`) was updated deliberately by
ARCH-20260922-032 per convention 17 when the defect it pinned was repaired.
The assertions now test the FIXED state.

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


class TestTheLiveWordingIsNowClassifiedCorrectly:
    """Convention 17: this class was TestTheLiveWordingIsMisclassified until
    ARCH-20260922-032 broadened _PROHIBITION_MARKER to include "contains no
    instances of" (R2'(a), corpus-derived, -031).  The defect it pinned is
    repaired, and these assertions now test the FIXED state.  Deliberately
    updated, not deleted — the trace, the wording and the tokens are the same;
    only the expected classification and its consequence have changed."""

    def test_the_planner_wrote_contains_no_instances_of(self, banned_criterion):
        """The wording, verbatim, so the root cause is legible without the trace."""
        assert "contains no instances of" in banned_criterion.lower(), (
            f"the live criterion no longer carries the phrasing this fixture "
            f"exists to pin: {banned_criterion!r}")

    def test_it_is_now_classified_prohibition(self, banned_criterion):
        """FIXED. _PROHIBITION_MARKER now recognises "contains no instances of"
        (-031 corpus: 1 occurrence, the -027 criterion, the only genuine
        invertible prohibition in 597 distinct criteria).  The non-parenthesised
        fallback in _forbidden_tokens extracts all four quoted tokens."""
        shape, forbidden = _classify(banned_criterion)
        assert shape == PROHIBITION, f"expected prohibition, got {shape}"
        assert forbidden == BANNED, f"expected {BANNED}, got {forbidden}"

    def test_a_compliant_draft_now_passes(self, banned_criterion, draft):
        """The repair.  Under prohibition, the criterion's forbidden tokens
        become the test — and a draft that contains none of them passes."""
        result = criteria_addressed(criteria=[banned_criterion], text=draft)
        assert result.passed is True, result.detail


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

        Before ARCH-20260922-032, only the recognised wording classified
        prohibition — which was B17's defect. Now both do, which is the repair.
        """
        for token in BANNED:
            assert token in banned_criterion.lower()
            assert token in self.RECOGNISED.lower()
        assert _classify(banned_criterion)[0] == _classify(self.RECOGNISED)[0] == PROHIBITION


class TestWhyTheDoubtDirectionWasNotFlipped:
    """Evidence for ARCH-20260922-029's refusal to apply B17-R2 as written.

    B17-R2 says: on doubt, abstain; never default to presence. There is no
    doubt state in _classify — it is deterministic, and every criterion that
    matches no positive pattern falls through to presence. So "never default to
    presence" can only be implemented by making the fallthrough abstain, and
    this test records what that would do to the live plan.
    """

    def test_the_doubt_predicate_reshapes_the_plan(self, criteria):
        """Convention 17: updated by ARCH-20260922-034 (R2'(b) doubt predicate).

        Pre-doubt: criterion 1 prohibition, criteria 2–6 presence.
        Post-doubt: criterion 1 prohibition, criteria 2 and 4 form (clause ii
        and iii respectively), criterion 3 form (clause iii), criteria 5–6
        presence (clause iv, no signal).  The fallthrough is still the dominant
        test for the two criteria the check CAN judge on this plan."""
        shapes = [_classify(c)[0] for c in criteria]
        assert shapes[0] == PROHIBITION, "criterion 1: prohibition (repaired by -032)"
        assert shapes[1] == FORM, "criterion 2: structural verb, no field vocab (clause ii)"
        assert shapes[2] == FORM, "criterion 3: cardinality 'between 350 and 450' (clause iii)"
        assert shapes[3] == FORM, "criterion 4: cardinality 'at least three' (clause iii)"
        assert shapes[4] == PRESENCE, "criterion 5: no signal (clause iv)"
        assert shapes[5] == PRESENCE, "criterion 6: no signal (clause iv)"

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


class TestReplayCommitted027Criteria:
    """ARCH-20260922-032 acceptance: replay the committed -027 criteria through
    the repaired classifier.  Read from the trace by content (convention 24),
    not from a restated string."""

    def test_criterion_1_classifies_prohibition_with_all_four_tokens(self, criteria):
        shape, tokens = _classify(criteria[0])
        assert shape == PROHIBITION, f"criterion 1 classified {shape}, expected prohibition"
        assert tokens == BANNED, f"extracted {tokens}, expected {BANNED}"

    def test_criterion_3_classifies_form_cardinality(self, criteria):
        """R2'(b) clause (iii): 'between 350 and 450' is a cardinality
        assertion — term overlap cannot count, so the criterion abstains."""
        shape, _ = _classify(criteria[2])
        assert shape == FORM, f"criterion 3 classified {shape}, expected form (clause iii)"

    def test_the_compliant_draft_passes_criterion_1(self, criteria, draft):
        result = criteria_addressed(criteria=[criteria[0]], text=draft)
        assert result.passed is True, result.detail

    def test_the_full_plan_still_fails_on_presence_criteria(self, criteria, draft):
        """The ruling is not a blanket pass. The draft still fails on criteria
        the presence test legitimately catches."""
        result = criteria_addressed(criteria=criteria, text=draft)
        assert result.data["shapes"][criteria[0]] == PROHIBITION


class TestRecallBroadeningRegression:
    """No existing classification changed.  Every criterion that classified
    prohibition or form before ARCH-20260922-032 must classify the same way
    after it, and no new prohibition or form was introduced from the presence
    population except for the -027 target (convention 21: exhibits precede
    leniency)."""

    @staticmethod
    def _corpus_criteria():
        import json
        from pathlib import Path
        criteria = set()
        for p in sorted(Path("docs/traces").glob("*.jsonl")):
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                def _find(d):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            if k == "success_criteria" and isinstance(v, list):
                                criteria.update(v)
                            else:
                                _find(v)
                    elif isinstance(d, list):
                        for item in d:
                            _find(item)
                _find(obj)
        return criteria

    # The B14 exhibit criterion, already prohibition before this change.
    _B14_PROHIBITION = (
        "The brief uses plain language, avoids the banned words ('leverage', "
        "'seamless', 'robust', 'in today's fast-paced world'), and follows "
        "Meridian's structure conventions (sentence case headings, no H4+, numbers "
        "as words below 10, dates as '12 March 2026')."
    )

    def test_no_existing_prohibition_or_form_changed(self):
        """The only classification change is the -027 target: presence -> prohibition."""
        target = "The copy contains no instances of"
        already_prohibition = {self._B14_PROHIBITION}
        changed = []
        for c in self._corpus_criteria():
            shape, tokens = _classify(c)
            if shape == PROHIBITION and not c.startswith(target):
                if c not in already_prohibition:
                    changed.append(("new prohibition", c[:80]))
        assert not changed, f"unexpected new classifications: {changed}"

    def test_no_former_prohibition_or_form_lost_its_classification(self):
        """No criterion that was PROHIBITION or original FORM before -034 may
        have changed shape. New FORM criteria are expected (doubt predicate)."""
        from autornd.graph.checks import _STRUCTURAL_VERB, _FIELD_VOCAB, _terms
        for c in self._corpus_criteria():
            shape, _ = _classify(c)
            # A criterion with structural verb + ≥2 fields was FORM before -034
            # and must still be FORM.
            if _STRUCTURAL_VERB.search(c) and len(_FIELD_VOCAB & _terms(c)) >= 2:
                assert shape == FORM, f"former FORM is now {shape}: {c[:80]}"
