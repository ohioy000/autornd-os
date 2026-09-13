"""Test verdict schema validation."""

import pytest
from pydantic import ValidationError

from autornd.models.verdicts import (
    Domain,
    ImplementVerdict,
    PlanVerdict,
    ReviewFinding,
    ReviewVerdict,
    RiskLevel,
    SpecialistRole,
    TriageVerdict,
    ValidateVerdict,
)


class TestTriageVerdict:
    def test_valid(self):
        v = TriageVerdict(
            domains=[Domain.FIRMWARE, Domain.HARDWARE],
            risk=RiskLevel.HIGH,
            specialists=[
                SpecialistRole.FIRMWARE_ENGINEER,
                SpecialistRole.HARDWARE_ENGINEER,
                SpecialistRole.TEST_ENGINEER,
            ],
            summary="New sensor node PCB revision",
        )
        assert v.risk == RiskLevel.HIGH
        assert len(v.specialists) == 3

    def test_rejects_invalid_domain(self):
        with pytest.raises(ValidationError):
            TriageVerdict(
                domains=["plumbing"],
                risk=RiskLevel.LOW,
                specialists=[SpecialistRole.BACKEND_ENGINEER],
                summary="test",
            )


class TestPlanVerdict:
    def test_ready_plan(self):
        v = PlanVerdict(
            ready=True,
            plan="Step 1: design schematic. Step 2: review.",
            success_criteria=["BOM < $45", "All pins assigned"],
        )
        assert v.ready
        assert v.cost_estimate is None
        assert len(v.success_criteria) == 2

    def test_blocked_plan(self):
        v = PlanVerdict(
            ready=False,
            plan="Cannot proceed",
            blockers=["Missing datasheet for XYZ sensor"],
        )
        assert not v.ready
        assert len(v.blockers) == 1


class TestImplementVerdict:
    def test_green(self):
        v = ImplementVerdict(
            done=True, green=True, iteration=1, summary="Implemented ADC read"
        )
        assert v.green
        assert v.red_cause is None

    def test_red(self):
        v = ImplementVerdict(
            done=True,
            green=False,
            red_cause="pin_conflict",
            iteration=2,
            summary="GPIO 18 used by both SPI and buzzer",
        )
        assert not v.green

    def test_iteration_bounds(self):
        with pytest.raises(ValidationError):
            ImplementVerdict(done=True, green=True, iteration=0, summary="bad")

    def test_iteration_allows_raised_max_iterations(self):
        """max_iterations is configurable to 20, so the verdict must not cap at 5."""
        v = ImplementVerdict(done=True, green=True, iteration=17, summary="ok")
        assert v.iteration == 17


class TestValidateVerdict:
    def test_green(self):
        v = ValidateVerdict(green=True, evidence=["All criteria pass"])
        assert v.green

    def test_red_with_evidence(self):
        v = ValidateVerdict(
            green=False,
            red_cause="bom_constraint",
            evidence=["Total BOM $47.20 exceeds target $42.50"],
        )
        assert not v.green
        assert "47.20" in v.evidence[0]


class TestReviewVerdict:
    def test_ship(self):
        v = ReviewVerdict(ship=True, findings=[], verdict="Ship with confidence")
        assert v.ship

    def test_blocked_with_findings(self):
        f = ReviewFinding(
            lens=SpecialistRole.FIRMWARE_ENGINEER,
            severity=RiskLevel.CRITICAL,
            detail="Deep sleep not returning to correct state",
        )
        v = ReviewVerdict(ship=False, findings=[f], verdict="Blocked on firmware issue")
        assert not v.ship
        assert len(v.findings) == 1
