"""`evidence` accepts the shape a live serving returns, and only that shape.

**The exhibit.** One run, one serving, twice in a row: the validator returned
`evidence` as an object keyed by criterion rather than a list of strings. The
schema refused it, `_rejection_note` fed the type error back, the next attempt
returned the same shape, and only the third succeeded. Two of eleven
engineering calls in that run bought nothing.

**Convention 21.** Shape variance that preserves information is coerced
deterministically and counted; shape variance that loses it is rejected. A
criterion-keyed object loses nothing, because the key is part of the finding.
A list mixing strings with other types, or an object with non-text keys or
values, means something this code cannot know, so the retry asks.

**Why the count matters.** The coercion is recorded through the same
normalisation counter as the green truth table, so nobody has to guess later
whether it is still needed — or notice too late that it started firing far more
than it used to. That is the §6.8 lesson: an instrument whose output nobody
keeps is not an instrument.

**Why no other field is coerced.** Exhibits precede leniency. `ReviewFinding`
earned eight aliases by losing three entire reviews first; this earns one fold
by costing two calls. The rejection log is what produces the next exhibit.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autornd.models.verdicts import (
    ValidateVerdict,
    normalisations,
    reset_normalisations,
)

# The two replies as the run log caught them. Their values are abbreviated —
# the log truncated them at the width it prints — but the shape is verbatim:
# a flat object, string keys, string values, one entry per criterion.
EXHIBIT_ONE = {
    "criterion_1": "FAIL — the clearance table omits two size combinations",
    "criterion_2": "PASS — the CTE is cited, and the same factor across sections",
}
EXHIBIT_TWO = {
    "criterion_1": "FAIL — section 3 and section 5 disagree on the bore minimum",
    "criterion_2": "PASS — the rounding is identical across sections",
}


@pytest.fixture(autouse=True)
def _fresh_counter():
    reset_normalisations()
    yield
    reset_normalisations()


@pytest.mark.parametrize("exhibit", [EXHIBIT_ONE, EXHIBIT_TWO])
def test_the_live_exhibits_coerce(exhibit):
    verdict = ValidateVerdict(green=False, red_cause="criterion 1 fails",
                              evidence=exhibit)
    assert verdict.evidence == [f"{k}: {v}" for k, v in exhibit.items()]
    assert all(isinstance(line, str) for line in verdict.evidence)


def test_the_fold_is_counted_as_a_normalisation():
    ValidateVerdict(green=False, red_cause="x", evidence=EXHIBIT_ONE)
    assert normalisations() == 1


def test_a_list_of_strings_is_left_alone_and_not_counted():
    verdict = ValidateVerdict(green=True, evidence=["criterion 1: PASS"])
    assert verdict.evidence == ["criterion 1: PASS"]
    assert normalisations() == 0


def test_ordering_is_natural_not_lexical():
    """`criterion_10` sorts after `criterion_2`, not between 1 and 2.

    Lexical order would make the same object fold differently depending on how
    many criteria a plan happened to have, which is exactly the kind of
    instability a retry must not introduce.
    """
    messy = {"criterion_10": "J", "criterion_2": "B", "criterion_1": "A"}
    verdict = ValidateVerdict(green=True, evidence=messy)
    assert verdict.evidence == ["criterion_1: A", "criterion_2: B",
                                "criterion_10: J"]


def test_the_fold_is_deterministic_across_retries():
    """Same content, different insertion order, same output."""
    forwards = {"c_1": "A", "c_2": "B", "c_3": "C"}
    backwards = {"c_3": "C", "c_2": "B", "c_1": "A"}
    assert (ValidateVerdict(green=True, evidence=forwards).evidence
            == ValidateVerdict(green=True, evidence=backwards).evidence)


def test_non_string_values_are_rejected_with_the_accepted_shapes_named():
    with pytest.raises(ValidationError) as caught:
        ValidateVerdict(green=True,
                        evidence={"criterion_1": {"status": "FAIL"}})
    message = str(caught.value)
    assert "list of strings" in message
    assert "non-string keys or values" in message
    assert normalisations() == 0


def test_non_string_keys_are_rejected():
    with pytest.raises(ValidationError):
        ValidateVerdict(green=True, evidence={1: "PASS"})


def test_a_mixed_list_is_rejected():
    """A list that is half strings is not a shape, it is a mistake."""
    with pytest.raises(ValidationError) as caught:
        ValidateVerdict(green=True, evidence=["criterion 1: PASS", {"c2": "x"}])
    assert "list of strings" in str(caught.value)


def test_an_empty_object_folds_to_an_empty_list():
    assert ValidateVerdict(green=True, evidence={}).evidence == []


def test_only_validate_evidence_is_folded():
    """No speculative coercion. The next fold needs its own exhibit."""
    from autornd.models.verdicts import ImplementVerdict

    with pytest.raises(ValidationError):
        ImplementVerdict(done=True, green=True, summary="s",
                         domain_concerns={"a": "b"})
