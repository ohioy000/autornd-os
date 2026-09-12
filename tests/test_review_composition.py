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
