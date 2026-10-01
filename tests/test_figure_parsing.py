"""F2 (ARCH-20261001-104): numbers_consistent reads a figure whole.

Exhibit: 102's Q3. The consistency check dissented on a correct answer with
"pa: plan says ['9'], implementation says ['800']": the plan's
'80.0 × 10^9 Pa' was read as 9 Pa and the implementation's '20,371,800 Pa'
as 800 Pa. Those texts are loaded from the committed trace, not retyped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autornd.graph import checks
from autornd.graph.checks import _figures, get_check

ROOT = Path(__file__).resolve().parent.parent
CONSISTENT = get_check("numbers_consistent")


def _q3() -> tuple[str, str]:
    lines = (json.loads(l) for l in
             (ROOT / "docs/traces/102-golden-arm-b.jsonl").read_text().splitlines() if l.strip())
    run = next(r for r in lines if r.get("scenario") == "golden_q3")
    return run["verdicts"]["plan"]["plan"], run["iterations"][0]["implement_summary"]


class TestAFigureIsReadWhole:
    @pytest.mark.parametrize("text,value", [
        ("80.0 × 10^9 Pa", 8.0e10), ("80.0 x 10^9 Pa", 8.0e10),
        ("6.14 × 10⁻⁷ m^4", 6.14e-7), ("1.5e-3 s", 1.5e-3),
        ("20,371,800 Pa", 20371800.0), ("0.2355 kg", 0.2355),
    ])
    def test_exponents_and_digit_groups_are_one_value(self, text, value):
        (got, _, _), *rest = _figures(text)
        assert got == pytest.approx(value)
        # An exponent or a digit group is never a value of its own.
        assert all(v != 9 and v != 800 for v, _, _ in rest)


class TestQ3IsNoLongerAFalseConflict:
    def test_102_q3_texts_pass(self):
        plan, implementation = _q3()
        result = CONSISTENT(plan=plan, implementation=implementation)
        assert result.passed, result.detail

    def test_a_real_conflict_still_fails(self):
        result = CONSISTENT(plan="Shear modulus 80.0 GPa.",
                            implementation="Shear modulus 70.0 GPa.")
        assert not result.passed and "gpa" in result.detail.lower()

    def test_agreement_is_at_the_less_precise_figure(self):
        result = CONSISTENT(plan="Max shear stress 20.4 MPa.",
                            implementation="Max shear stress 20.3718 MPa.")
        assert result.passed, result.detail

    def test_the_old_reading_makes_q3_fail_again(self, monkeypatch):
        """The break: read figures with the old _NUMBER pattern."""
        def old(text):
            return [(float(v), 99, u) for v, u in checks._NUMBER.findall(text or "")]
        monkeypatch.setattr(checks, "_figures", old)
        plan, implementation = _q3()
        result = CONSISTENT(plan=plan, implementation=implementation)
        assert not result.passed
        assert "pa: plan says" in result.detail
