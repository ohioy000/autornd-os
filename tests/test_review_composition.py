"""Test risk-based review team composition and triage enforcement."""

import pytest

from autornd.engine.phases import lead_for_domain
from autornd.engine.review_composition import get_review_team
from autornd.engine.workflow import WorkflowEngine
from autornd.models.verdicts import Domain, RiskLevel, SpecialistRole, TriageVerdict


class TestReviewComposition:
    """The team is derived from who triage assigned, and risk decides how much
    scrutiny is added on top.

    The old fixed table returned every existing role at `critical`, which over
    thirty-six sectors meant seven engineers reviewing a records retention
    schedule — a cost with no accuracy behind it.
    """

    def test_critical_covers_the_assignees_plus_architect_and_tester(self):
        team = get_review_team(RiskLevel.CRITICAL, [Domain.FIRMWARE],
                               [SpecialistRole.FIRMWARE_ENGINEER])
        assert SpecialistRole.FIRMWARE_ENGINEER in team
        assert SpecialistRole.SYSTEMS_ARCHITECT in team
        assert SpecialistRole.TEST_ENGINEER in team

    def test_critical_no_longer_drags_in_every_role(self):
        """The specific regression: a non-engineering request should not buy an
        engineering department."""
        team = get_review_team(RiskLevel.CRITICAL, ["legal_ops"], ["paralegal"])
        assert "paralegal" in team
        assert SpecialistRole.FRONTEND_ENGINEER not in team
        assert SpecialistRole.HARDWARE_ENGINEER not in team
        assert len(team) == 3

    def test_critical_represents_a_domain_triage_left_unstaffed(self):
        """At this level an unrepresented domain is the gap that matters, so its
        declared lead is present even when triage did not assign one."""
        team = get_review_team(RiskLevel.CRITICAL, [Domain.HARDWARE],
                               [SpecialistRole.BACKEND_ENGINEER])
        assert SpecialistRole.HARDWARE_ENGINEER in team

    def test_high_hardware_includes_hw_test_arch(self):
        team = get_review_team(RiskLevel.HIGH, [Domain.HARDWARE],
                               [SpecialistRole.HARDWARE_ENGINEER])
        assert SpecialistRole.HARDWARE_ENGINEER in team
        assert SpecialistRole.TEST_ENGINEER in team
        assert SpecialistRole.SYSTEMS_ARCHITECT in team
        assert SpecialistRole.FRONTEND_ENGINEER not in team

    def test_high_firmware_includes_fw_test_arch(self):
        team = get_review_team(RiskLevel.HIGH, [Domain.FIRMWARE],
                               [SpecialistRole.FIRMWARE_ENGINEER])
        assert SpecialistRole.FIRMWARE_ENGINEER in team
        assert SpecialistRole.TEST_ENGINEER in team
        assert SpecialistRole.SYSTEMS_ARCHITECT in team
        assert SpecialistRole.FRONTEND_ENGINEER not in team

    def test_medium_backend_includes_backend_test(self):
        team = get_review_team(RiskLevel.MEDIUM, [Domain.BACKEND],
                               [SpecialistRole.BACKEND_ENGINEER])
        assert SpecialistRole.BACKEND_ENGINEER in team
        assert SpecialistRole.TEST_ENGINEER in team

    def test_medium_does_not_buy_an_architect(self):
        """Medium work is reversible; a system-level view is what high is for."""
        team = get_review_team(RiskLevel.MEDIUM, [Domain.BACKEND],
                               [SpecialistRole.BACKEND_ENGINEER])
        assert SpecialistRole.SYSTEMS_ARCHITECT not in team

    def test_medium_infra_falls_back_to_the_domain_lead(self):
        """An unstaffed request still gets the right reviewer, not an arbitrary
        one — infrastructure leads to the architect."""
        team = get_review_team(RiskLevel.MEDIUM, [Domain.INFRASTRUCTURE], [])
        assert SpecialistRole.SYSTEMS_ARCHITECT in team
        assert SpecialistRole.TEST_ENGINEER in team

    def test_low_frontend_is_frontend_only(self):
        team = get_review_team(RiskLevel.LOW, [Domain.FRONTEND],
                               [SpecialistRole.FRONTEND_ENGINEER])
        assert team == [SpecialistRole.FRONTEND_ENGINEER]

    def test_low_is_one_reviewer_and_never_just_the_tester(self):
        """A single reviewer at low risk should be someone who can judge the
        work, not only someone who checks it."""
        team = get_review_team(RiskLevel.LOW, ["marketing"],
                               ["copywriter", SpecialistRole.TEST_ENGINEER])
        assert team == ["copywriter"]

    def test_low_unstaffed_honours_the_declared_domain_lead(self):
        """The old table ignored the lead map at low risk and always answered
        architect. Following the declaration is the consistent behaviour — and
        it is what lets a profile decide who reviews its own domains."""
        team = get_review_team(RiskLevel.LOW, [Domain.DOCUMENTATION], [])
        assert team == [lead_for_domain(Domain.DOCUMENTATION)]

    def test_low_with_no_domain_at_all_is_the_architect(self):
        assert get_review_team(RiskLevel.LOW, [], []) == [
            SpecialistRole.SYSTEMS_ARCHITECT]

    def test_the_team_is_order_stable(self):
        """Two identical runs must not look different."""
        args = (RiskLevel.CRITICAL, ["hardware", "legal_ops"],
                ["paralegal", "hardware_engineer"])
        assert get_review_team(*args) == get_review_team(*args)


class TestTriageEnforcement:
    def test_high_risk_adds_test_engineer(self):
        verdict = TriageVerdict(
            domains=[Domain.FIRMWARE],
            risk=RiskLevel.HIGH,
            specialists=[SpecialistRole.FIRMWARE_ENGINEER],
            summary="test",
        )
        WorkflowEngine._enforce_triage_composition(verdict)
        assert SpecialistRole.TEST_ENGINEER in verdict.specialists

    def test_critical_risk_adds_test_engineer(self):
        verdict = TriageVerdict(
            domains=[Domain.HARDWARE],
            risk=RiskLevel.CRITICAL,
            specialists=[SpecialistRole.HARDWARE_ENGINEER],
            summary="test",
        )
        WorkflowEngine._enforce_triage_composition(verdict)
        assert SpecialistRole.TEST_ENGINEER in verdict.specialists

    def test_multi_domain_adds_architect(self):
        verdict = TriageVerdict(
            domains=[Domain.FIRMWARE, Domain.BACKEND],
            risk=RiskLevel.MEDIUM,
            specialists=[SpecialistRole.FIRMWARE_ENGINEER, SpecialistRole.BACKEND_ENGINEER],
            summary="test",
        )
        WorkflowEngine._enforce_triage_composition(verdict)
        assert SpecialistRole.SYSTEMS_ARCHITECT in verdict.specialists

    def test_no_duplicate_when_already_present(self):
        verdict = TriageVerdict(
            domains=[Domain.FIRMWARE],
            risk=RiskLevel.HIGH,
            specialists=[SpecialistRole.FIRMWARE_ENGINEER, SpecialistRole.TEST_ENGINEER],
            summary="test",
        )
        WorkflowEngine._enforce_triage_composition(verdict)
        assert verdict.specialists.count(SpecialistRole.TEST_ENGINEER) == 1

    def test_low_risk_single_domain_unchanged(self):
        verdict = TriageVerdict(
            domains=[Domain.FRONTEND],
            risk=RiskLevel.LOW,
            specialists=[SpecialistRole.FRONTEND_ENGINEER],
            summary="test",
        )
        original = list(verdict.specialists)
        WorkflowEngine._enforce_triage_composition(verdict)
        assert verdict.specialists == original


class TestUnrecognisedDomains:
    """R&D names subjects no shipped list contains. An unfamiliar domain must
    not silently get a smaller team than a familiar one — it is the case that
    most wants a generalist and someone to check the work."""

    def test_an_unknown_domain_pulls_in_architect_and_test_at_medium(self):
        team = get_review_team(RiskLevel.MEDIUM, ["mechanical"])
        assert SpecialistRole.SYSTEMS_ARCHITECT in team
        assert SpecialistRole.TEST_ENGINEER in team

    def test_an_unknown_domain_does_not_crash_at_any_risk(self):
        for risk in RiskLevel:
            team = get_review_team(risk, ["astrophysics", "food_safety"])
            assert team, f"empty team at {risk}"

    def test_known_domains_are_unaffected(self):
        assert get_review_team(RiskLevel.LOW, ["frontend"]) == [
            SpecialistRole.FRONTEND_ENGINEER]
        high = get_review_team(RiskLevel.HIGH, ["hardware"])
        assert SpecialistRole.HARDWARE_ENGINEER in high

    def test_plain_strings_and_enum_members_agree(self):
        assert get_review_team(RiskLevel.HIGH, ["hardware"]) == \
               get_review_team(RiskLevel.HIGH, [Domain.HARDWARE])

    def test_mixed_known_and_unknown_keeps_the_known_specialists(self):
        team = get_review_team(RiskLevel.MEDIUM, ["backend", "acoustics"])
        assert SpecialistRole.BACKEND_ENGINEER in team
        assert SpecialistRole.SYSTEMS_ARCHITECT in team


class TestLeadForDomain:
    """Leads are normalised role names. They compare equal to the shipped enum
    members, because those subclass str — but they are no longer restricted to
    them, since a profile may declare its own roles."""

    def test_a_known_domain_resolves_to_its_specialist(self):
        from autornd.engine.phases import lead_for_domain

        assert lead_for_domain("firmware") == SpecialistRole.FIRMWARE_ENGINEER
        assert lead_for_domain(Domain.BACKEND) == SpecialistRole.BACKEND_ENGINEER

    def test_an_unknown_domain_resolves_to_the_architect(self):
        """Not an error. Cross-domain and unfamiliar work is that role's job."""
        from autornd.engine.phases import lead_for_domain

        assert lead_for_domain("mechanical") == SpecialistRole.SYSTEMS_ARCHITECT

    def test_a_profile_declared_domain_wins(self, monkeypatch):
        from autornd.engine.phases import lead_for_domain
        from autornd.profiles import ProjectProfile, set_profile

        set_profile(ProjectProfile(
            name="Test", domains={"Mechanical": "hardware_engineer"}))
        try:
            assert lead_for_domain("mechanical") == SpecialistRole.HARDWARE_ENGINEER
        finally:
            from autornd.profiles import DEFAULT_PROFILE
            set_profile(DEFAULT_PROFILE)

    def test_a_profile_role_outside_the_enum_is_honoured(self):
        """Found live: a profile mapping `legal_ops` to `paralegal` reviewed
        with the architect instead, because the lead was validated against the
        shipped enum. The roster is a default, not a limit."""
        from autornd.engine.phases import lead_for_domain
        from autornd.profiles import DEFAULT_PROFILE, ProjectProfile, set_profile

        set_profile(ProjectProfile(
            name="Chambers",
            domains={"legal_ops": {"lead": "paralegal"}},
            roles={"paralegal": {"name": "Paralegal"}}))
        try:
            assert lead_for_domain("legal_ops") == "paralegal"
        finally:
            set_profile(DEFAULT_PROFILE)

    def test_an_undeclared_lead_still_resolves_to_a_specialist(self):
        """Even a lead the profile names without declaring must produce a
        working specialist rather than raising."""
        from autornd.engine.phases import lead_for_domain
        from autornd.profiles import DEFAULT_PROFILE, ProjectProfile, set_profile
        from autornd.specialists.registry import get_specialist

        set_profile(ProjectProfile(name="T", domains={"optics": "wizard"}))
        try:
            lead = lead_for_domain("optics")
            assert lead == "wizard"
            assert get_specialist(lead).name == "Wizard"
        finally:
            set_profile(DEFAULT_PROFILE)
