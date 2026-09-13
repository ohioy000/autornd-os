"""Test verdict schema validation."""

import pytest
from pydantic import ValidationError

from autornd.models.verdicts import (
    Domain,
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

    def test_accepts_a_domain_outside_the_default_vocabulary(self):
        """Domains are open-ended by design. Measured over twelve subjects,
        nine had no fitting label in the enum and eight were forced onto
        "hardware" — civil engineering as hardware, a latency budget as
        firmware. Rejecting an unlisted domain is what caused that."""
        v = TriageVerdict(
            domains=["plumbing"],
            risk=RiskLevel.LOW,
            specialists=[SpecialistRole.BACKEND_ENGINEER],
            summary="test",
        )
        assert v.domains == ["plumbing"]

    def test_domains_are_normalised_and_deduped(self):
        v = TriageVerdict(
            domains=[Domain.HARDWARE, "Mechanical", "mechanical", "food safety", "  "],
            risk=RiskLevel.MEDIUM,
            specialists=[SpecialistRole.HARDWARE_ENGINEER],
            summary="test",
        )
        assert v.domains == ["hardware", "mechanical", "food_safety"]

    def test_enum_members_still_work(self):
        """Every existing caller passes Domain members; they must keep working."""
        v = TriageVerdict(
            domains=[Domain.BACKEND],
            risk=RiskLevel.MEDIUM,
            specialists=[SpecialistRole.BACKEND_ENGINEER],
            summary="test",
        )
        assert v.domains == ["backend"]


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


class TestPlanCriteriaRequired:
    """Regression: a ready plan with no success criteria left the validator
    nothing to check, so it could never return green and the loop burned every
    iteration before escalating."""

    def test_placeholder_criteria_are_rejected(self):
        """The exact failure seen in a live run: the architecture model returned
        four literal '...' strings, which passed a non-empty check and left the
        validator nothing to judge, so the loop could never go green."""
        with pytest.raises(ValidationError, match="placeholder"):
            PlanVerdict(ready=True, plan="p", blockers=[],
                        success_criteria=["...", "...", "...", "..."])

    @pytest.mark.parametrize("crit", [["TBD", "TBD"], ["criterion 1", "criterion 2"],
                                      [""], ["…"], ["placeholder"]])
    def test_other_degenerate_criteria_rejected(self, crit):
        with pytest.raises(ValidationError):
            PlanVerdict(ready=True, plan="p", blockers=[], success_criteria=crit)

    @pytest.mark.parametrize("crit", ["BOM < $45", "All pins assigned",
                                      "Backoff capped at 60s with jitter"])
    def test_real_criteria_survive_the_guard(self, crit):
        """Short but concrete criteria must not be rejected — a false positive
        here costs a plan retry for no reason."""
        v = PlanVerdict(ready=True, plan="p", blockers=[], success_criteria=[crit])
        assert v.success_criteria == [crit]

    def test_ready_plan_without_criteria_is_rejected(self):
        with pytest.raises(ValidationError, match="success_criteria"):
            PlanVerdict(ready=True, plan="do the thing", blockers=[],
                        success_criteria=[])

    def test_ready_plan_with_criteria_is_fine(self):
        v = PlanVerdict(ready=True, plan="do the thing", blockers=[],
                        success_criteria=["backoff capped at 60s"])
        assert v.success_criteria == ["backoff capped at 60s"]

    def test_blocked_plan_needs_no_criteria(self):
        v = PlanVerdict(ready=False, plan="cannot proceed",
                        blockers=["missing datasheet"], success_criteria=[])
        assert not v.ready


class TestBlockedPlansAreValid:
    """Regression from a live run: the architect correctly refused to plan an
    underspecified battery change, returning ready=false with detailed blockers
    and no plan text. The schema required `plan`, so it was rejected three
    times — the model was right and the type was wrong."""

    LIVE_FAILURE = {
        "ready": False,
        "blockers": ["Battery chemistry, voltage and capacity are unspecified, "
                     "so safe cutoff voltages cannot be computed."],
        "success_criteria": [],
    }

    def test_the_live_refusal_is_accepted(self):
        v = PlanVerdict(**self.LIVE_FAILURE)
        assert not v.ready and v.plan == ""

    def test_a_block_must_say_why(self):
        with pytest.raises(ValidationError, match="blockers"):
            PlanVerdict(ready=False, blockers=[], success_criteria=[])

    def test_a_ready_plan_still_needs_plan_text(self):
        with pytest.raises(ValidationError, match="plan itself"):
            PlanVerdict(ready=True, plan="   ", blockers=[],
                        success_criteria=["Backoff capped at 60s"])


class TestOpenRoster:
    """Triage returned `infrastructure_engineer` and the domain value
    `documentation` in the specialists field. The roster is a default, not a
    limit, so both are accepted and normalised rather than failing the call."""

    def test_a_role_outside_the_enum_is_accepted(self):
        v = TriageVerdict(domains=["appsec"], risk="high",
                          specialists=["infrastructure_engineer"], summary="s")
        assert v.specialists == ["infrastructure_engineer"]

    def test_roles_are_normalised_and_deduplicated(self):
        v = TriageVerdict(domains=["legal_ops"], risk="medium",
                          specialists=["Paralegal", "paralegal", " PARALEGAL "],
                          summary="s")
        assert v.specialists == ["paralegal"]

    def test_enum_members_still_work(self):
        v = TriageVerdict(domains=["backend"], risk="low",
                          specialists=[SpecialistRole.BACKEND_ENGINEER], summary="s")
        assert v.specialists == ["backend_engineer"]
        assert SpecialistRole.BACKEND_ENGINEER in v.specialists

    def test_blank_roles_are_dropped(self):
        v = TriageVerdict(domains=["backend"], risk="low",
                          specialists=["", "  ", "backend_engineer"], summary="s")
        assert v.specialists == ["backend_engineer"]


class TestUnrecallable:
    """A separate axis from risk. A signed rollout to 40,000 devices harms
    nobody — it classifies `high` 3/3, correctly — and cannot be taken back."""

    def test_it_defaults_to_false(self):
        v = TriageVerdict(domains=["backend"], risk="low",
                          specialists=["backend_engineer"], summary="s")
        assert v.unrecallable is False

    def test_it_is_independent_of_risk(self):
        v = TriageVerdict(domains=["firmware"], risk="high",
                          specialists=["firmware_engineer"],
                          unrecallable=True, summary="s")
        assert v.risk == RiskLevel.HIGH and v.unrecallable is True
