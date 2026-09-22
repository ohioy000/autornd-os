"""Convention 28, made executable: every documentation guard must fail on an
empty document.

**Why this exists.** Five instruments failed on 2026-09-22 and four of them
could not fail at all (§33.2). The sharpest was a provenance guard whose regex
used `\\s*` where `HANDOVER.md` reads ``**HEAD:** `sha` ``. It matched nothing,
`findall` returned `[]`, every check below iterated an empty list, and **all
three deliberate break attempts printed `3 passed`**. It was caught by running
the breaks and reading the output — which nothing required, and which the next
guard's author will not necessarily do.

So the property is asserted rather than remembered. A guard that reads
`HANDOVER.md` is handed an **empty string** and must raise. If it passes, it was
never checking the document; it was checking that nothing contradicted it, and
those are different claims.

**The bound on this.** Emptiness is the weakest possible absence and catching it
proves only that the guard looked. It does not prove the guard looks at the
*right* thing — that is each guard's own job and its own tests. This file closes
one class, not all of them.
"""

from __future__ import annotations

import inspect

import pytest

import tests.test_handover_truth as truth


# A guard whose assertion is PURELY NEGATIVE — "none of these forbidden strings
# appears" — is satisfied by an empty document by construction, and that is
# correct behaviour rather than a defect. It is exempt, by name, with its
# reason, and the exemption is asserted to stay tiny below.
#
# The residual risk is named rather than waved away: if `HANDOVER.md` were
# emptied, this one guard would pass. Every other guard in the class would
# fail, so the document's disappearance is still caught — by the class, not by
# this member of it.
PURELY_NEGATIVE = {
    "test_retired_claims_are_not_reasserted":
        "asserts that measurement-retired claims do NOT appear; an empty "
        "document reasserts nothing, which is a true answer",
}


def _document_guards():
    """Every guard in test_handover_truth that reads the document.

    Discovered by signature rather than listed, so a guard added tomorrow is
    covered without anyone remembering to add it here — which is the same
    failure mode one level up.
    """
    found = []
    for name, fn in vars(truth).items():
        if not name.startswith("test_") or not callable(fn):
            continue
        params = inspect.signature(fn).parameters
        if "handover" in params and len(params) == 1:
            found.append((name, fn))
    return sorted(found)


def test_there_are_document_guards_to_check():
    """Convention 28 applied to this file itself. If the discovery above ever
    returns nothing — a rename, a refactor, a moved module — every
    parametrised case below would silently vanish and this file would pass
    while checking nothing at all."""
    guards = _document_guards()
    assert len(guards) >= 5, (
        f"expected the HANDOVER truth guards to be discoverable; found "
        f"{[n for n, _ in guards]}. If they moved, this file is now vacuous.")


def test_the_exemption_list_stays_small():
    """An exemption list is how a rule dies quietly. This one holds guards that
    are correct to pass on nothing; if it grows, the rule is being managed
    rather than applied."""
    assert len(PURELY_NEGATIVE) <= 2, (
        f"{len(PURELY_NEGATIVE)} guards are exempt from Convention 28. Each "
        f"needs a reason that is about the guard's logic, not about the "
        f"inconvenience of fixing it: {sorted(PURELY_NEGATIVE)}")
    for name in PURELY_NEGATIVE:
        assert name in dict(_document_guards()), (
            f"{name} is exempted but no longer exists — a stale exemption is a "
            f"hole waiting for a guard of the same name")


@pytest.mark.parametrize(
    "name,fn",
    [(n, f) for n, f in _document_guards() if n not in PURELY_NEGATIVE],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_the_guard_fails_on_an_empty_document(name, fn):
    """Hand the guard nothing and watch it object."""
    with pytest.raises(BaseException) as caught:
        fn("")
    assert not isinstance(caught.value, (TypeError, NameError)), (
        f"{name} raised {type(caught.value).__name__} rather than failing its "
        f"assertion — it broke instead of objecting, which is not the same "
        f"thing and hides what it would have said")
