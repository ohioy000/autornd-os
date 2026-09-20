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
    expected = render(derive(ROOT / "docs" / "traces"))
    assert expected in LEDGER.read_text(encoding="utf-8"), (
        "docs/serving-ledger.md has drifted from docs/traces/. It is generated, "
        "not written — regenerate it. The derived table is:\n\n" + expected)


def test_the_ledger_covers_every_trace_that_declares_a_pin():
    """A guard that only compared strings would pass on an empty derivation."""
    combos = derive(ROOT / "docs" / "traces")
    assert combos, "no (tier, model, serving) rows derived — the traces moved or changed shape"
    total = sum(sum(c.values()) for c in combos.values())
    assert total > 100, f"only {total} pinned units derived; the corpus is larger than that"


def test_the_model_is_part_of_the_key():
    """A pin is not portable without its map — the exhibit is architecture on
    StreamLake, which completes against one model and cannot resolve against
    another. If the key ever collapses to (tier, serving), that lesson is lost."""
    combos = derive(ROOT / "docs" / "traces")
    assert all(len(k) == 3 for k in combos)
    models_per_pin: dict[tuple[str, str], set[str]] = {}
    for tier, model, provider in combos:
        models_per_pin.setdefault((tier, provider), set()).add(model)
    assert any(len(v) > 1 for v in models_per_pin.values()), (
        "no serving in the corpus has run two different models — if that is now "
        "true, this guard is measuring nothing and should be re-thought")
