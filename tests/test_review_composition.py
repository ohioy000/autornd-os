"""Test risk-based review team composition and triage enforcement."""

import pytest

from autornd.engine.review_composition import get_review_team
from autornd.engine.workflow import WorkflowEngine
from autornd.models.verdicts import Domain, RiskLevel, SpecialistRole, TriageVerdict


class TestReviewComposition:
    def test_critical_includes_all_specialists(self):
        team = get_review_team(RiskLevel.CRITICAL, [Domain.FIRMWARE])
        assert set(team) == set(SpecialistRole)

    def test_high_hardware_includes_hw_supply_test_arch(self):
        team = get_review_team(RiskLevel.HIGH, [Domain.HARDWARE])
        assert SpecialistRole.HARDWARE_ENGINEER in team
        assert SpecialistRole.SUPPLY_CHAIN in team
        assert SpecialistRole.TEST_ENGINEER in team
        assert SpecialistRole.SYSTEMS_ARCHITECT in team
        assert SpecialistRole.FRONTEND_ENGINEER not in team

    def test_high_firmware_includes_fw_test_arch(self):
        team = get_review_team(RiskLevel.HIGH, [Domain.FIRMWARE])
        assert SpecialistRole.FIRMWARE_ENGINEER in team
        assert SpecialistRole.TEST_ENGINEER in team
        assert SpecialistRole.SYSTEMS_ARCHITECT in team
        assert SpecialistRole.FRONTEND_ENGINEER not in team

    def test_medium_backend_includes_backend_test(self):
        team = get_review_team(RiskLevel.MEDIUM, [Domain.BACKEND])
        assert SpecialistRole.BACKEND_ENGINEER in team
        assert SpecialistRole.TEST_ENGINEER in team

    def test_medium_infra_includes_backend_arch(self):
        team = get_review_team(RiskLevel.MEDIUM, [Domain.INFRASTRUCTURE])
        assert SpecialistRole.BACKEND_ENGINEER in team
        assert SpecialistRole.SYSTEMS_ARCHITECT in team

    def test_low_frontend_is_frontend_only(self):
        team = get_review_team(RiskLevel.LOW, [Domain.FRONTEND])
        assert team == [SpecialistRole.FRONTEND_ENGINEER]

    def test_low_docs_is_architect_only(self):
        team = get_review_team(RiskLevel.LOW, [Domain.DOCUMENTATION])
        assert team == [SpecialistRole.SYSTEMS_ARCHITECT]


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
    def test_a_known_domain_resolves_to_its_specialist(self):
        from autornd.engine.phases import lead_for_domain

        assert lead_for_domain("firmware") is SpecialistRole.FIRMWARE_ENGINEER
        assert lead_for_domain(Domain.BACKEND) is SpecialistRole.BACKEND_ENGINEER

    def test_an_unknown_domain_resolves_to_the_architect(self):
        """Not an error. Cross-domain and unfamiliar work is that role's job."""
        from autornd.engine.phases import lead_for_domain

        assert lead_for_domain("mechanical") is SpecialistRole.SYSTEMS_ARCHITECT

    def test_a_profile_declared_domain_wins(self, monkeypatch):
        from autornd.engine.phases import lead_for_domain
        from autornd.profiles import ProjectProfile, set_profile

        set_profile(ProjectProfile(
            name="Test", domains={"Mechanical": "hardware_engineer"}))
        try:
            assert lead_for_domain("mechanical") is SpecialistRole.HARDWARE_ENGINEER
        finally:
            from autornd.profiles import DEFAULT_PROFILE
            set_profile(DEFAULT_PROFILE)

    def test_a_profile_mapping_to_a_bad_role_falls_back(self, monkeypatch):
        from autornd.engine.phases import lead_for_domain
        from autornd.profiles import ProjectProfile, set_profile

        set_profile(ProjectProfile(name="Test", domains={"optics": "wizard"}))
        try:
            assert lead_for_domain("optics") is SpecialistRole.SYSTEMS_ARCHITECT
        finally:
            from autornd.profiles import DEFAULT_PROFILE
            set_profile(DEFAULT_PROFILE)
