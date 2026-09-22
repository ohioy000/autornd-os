"""`docs/serving-ledger.md` must not drift from the traces it is derived from.

The fourth generated-or-guarded fact in this repo, and the one that had gone
uncollected longest: which serving has run which tier, and how it went. It was
spread across §6.1, §6.11, B4's row, the B12 traces and two pre-registrations,
so every session re-derived it from trace headers — twice at the cost of a live
run, and once producing a wrong disqualification that 233 committed units
already contradicted.
"""

from __future__ import annotations

from pathlib import Path

from tests.serving_ledger import derive, render

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "serving-ledger.md"


def test_the_committed_table_is_the_derived_one():
    combos, tiers = derive(ROOT / "docs" / "traces")
    expected = render(combos, tiers)
    assert expected in LEDGER.read_text(encoding="utf-8"), (
        "docs/serving-ledger.md has drifted from docs/traces/. It is generated, "
        "not written — regenerate it. The derived table is:\n\n" + expected)


def test_the_ledger_covers_every_trace_that_declares_a_pin():
    """A guard that only compared strings would pass on an empty derivation."""
    combos, _ = derive(ROOT / "docs" / "traces")
    assert combos, "no (tier, model, serving) rows derived — the traces moved or changed shape"
    total = sum(sum(c.values()) for c in combos.values())
    assert total > 100, f"only {total} pinned units derived; the corpus is larger than that"


def test_the_model_is_part_of_the_key():
    """A pin is not portable without its map — the exhibit is architecture on
    StreamLake, which completes against one model and cannot resolve against
    another. If the key ever collapses to (tier, serving), that lesson is lost."""
    combos, _ = derive(ROOT / "docs" / "traces")
    assert all(len(k) == 4 for k in combos)
    models_per_pin: dict[tuple[str, str], set[str]] = {}
    for tier, model, provider, _pinned in combos:
        models_per_pin.setdefault((tier, provider), set()).add(model)
    assert any(len(v) > 1 for v in models_per_pin.values()), (
        "no serving in the corpus has run two different models — if that is now "
        "true, this guard is measuring nothing and should be re-thought")


def test_no_tier_can_be_silently_absent():
    """Convention 28, and this ledger is its canonical exhibit.

    The table used to walk the header's PINS and skip an empty one, so an
    unpinned tier produced no row and the rendered table carried three tiers
    while looking complete. The tier it was missing was `escalation` — 70-78%
    of hard-trace spend (§6.10), and $0.1080 of $0.1547 on a single 2026-09-22
    run. The most expensive tier in the system was the one the instrument could
    not see, and nothing said so.
    """
    combos, tiers = derive(ROOT / "docs" / "traces")
    assert tiers, "no tiers derived at all — the headers moved or changed shape"

    rendered = render(combos, tiers)
    for tier in tiers:
        assert f"`{tier}`" in rendered, (
            f"tier {tier!r} appears in a trace header's model map but nowhere "
            f"in the rendered table — not as a row and not as unmeasured. An "
            f"absent row reads as a tier that does not exist.")


def test_escalation_has_rows_and_not_merely_a_mention():
    """The specific tier this repair exists for.

    The first version of this guard asserted "`escalation`" appeared in the
    rendered text — and it PASSED with the blind spot deliberately restored,
    because the "Unmeasured tiers" line names the tier too. A guard satisfied
    by the sentence that says a thing is missing is convention 28 one more
    time, found by breaking the derivation and reading the result rather than
    trusting the guard.
    """
    combos, tiers = derive(ROOT / "docs" / "traces")
    assert "escalation" in tiers

    rows = [k for k in combos if k[0] == "escalation"]
    assert rows, (
        "escalation has no row in the ledger. It is 70-78% of hard-trace spend "
        "(§6.10) and was invisible here until 2026-09-22.")
    units = sum(sum(combos[k].values()) for k in rows)
    assert units >= 10, (
        f"only {units} escalation units derived; the committed traces hold "
        f"more than that and the derivation is dropping them again")

    rendered = render(combos, tiers)
    data_rows = [ln for ln in rendered.splitlines()
                 if ln.startswith("| `escalation`")]
    assert data_rows, "escalation is named but has no table row"


def test_rotated_and_pinned_evidence_is_not_folded_together():
    """The same provider can serve a tier both ways, and reporting one number
    for both would claim a pin's evidence for rotation's."""
    combos, _ = derive(ROOT / "docs" / "traces")
    by_arm: dict[tuple[str, str, str], set[bool]] = {}
    for tier, model, provider, pinned in combos:
        by_arm.setdefault((tier, model, provider), set()).add(pinned)
    both = {k for k, v in by_arm.items() if len(v) > 1}
    assert all(len(k) == 3 for k in by_arm)
    # `assert isinstance(both, set)` was the first version of this line and it
    # could not fail — convention 28, inside the change that makes this ledger
    # the convention's exhibit. The corpus does contain arms served both ways
    # (GMICloud and DigitalOcean each ran `engineering` pinned and rotated), so
    # the distinction is real and is asserted rather than merely representable.
    assert both, (
        "no arm in the corpus has been served both pinned and rotated. If that "
        "is now true this guard measures nothing; if it is not, the key has "
        "collapsed and pinned evidence is being folded into rotated evidence")


def test_the_pinned_rows_kept_their_numbers():
    """The repair must add arms, never move the ones already published."""
    combos, _ = derive(ROOT / "docs" / "traces")
    gmicloud = next(
        (c for (tier, model, prov, pinned), c in combos.items()
         if tier == "engineering" and prov == "GMICloud" and pinned
         and "flash" in model),
        None,
    )
    assert gmicloud is not None, "the GMICloud engineering pin vanished"
    assert sum(gmicloud.values()) >= 240, (
        f"GMICloud's pinned engineering n moved to {sum(gmicloud.values())}; "
        f"the published figure was 243 and this repair must not touch it")
