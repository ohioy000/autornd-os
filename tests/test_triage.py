"""Test triage classification and specialist routing."""

import pytest

from autornd.models.verdicts import Domain, RiskLevel, SpecialistRole, TriageVerdict


class TestTriageClassification:
    def test_firmware_request_routes_correctly(self):
        verdict = TriageVerdict(
            domains=[Domain.FIRMWARE],
            risk=RiskLevel.HIGH,
            specialists=[
                SpecialistRole.FIRMWARE_ENGINEER,
                SpecialistRole.TEST_ENGINEER,
                SpecialistRole.SYSTEMS_ARCHITECT,
            ],
            summary="LoRa deep sleep state machine redesign",
        )
        assert Domain.FIRMWARE in verdict.domains
        assert SpecialistRole.FIRMWARE_ENGINEER in verdict.specialists
        assert SpecialistRole.TEST_ENGINEER in verdict.specialists

    def test_multi_domain_includes_architect(self):
        verdict = TriageVerdict(
            domains=[Domain.FIRMWARE, Domain.BACKEND],
            risk=RiskLevel.MEDIUM,
            specialists=[
                SpecialistRole.FIRMWARE_ENGINEER,
                SpecialistRole.BACKEND_ENGINEER,
                SpecialistRole.SYSTEMS_ARCHITECT,
            ],
            summary="Change MQTT payload encoding",
        )
        assert SpecialistRole.SYSTEMS_ARCHITECT in verdict.specialists

    def test_critical_risk_flags_safety(self):
        verdict = TriageVerdict(
            domains=[Domain.HARDWARE],
            risk=RiskLevel.CRITICAL,
            specialists=[
                SpecialistRole.HARDWARE_ENGINEER,
                SpecialistRole.TEST_ENGINEER,
                SpecialistRole.SUPPLY_CHAIN,
                SpecialistRole.SYSTEMS_ARCHITECT,
            ],
            summary="LiFePO4 battery integration for livestock tag",
        )
        assert verdict.risk == RiskLevel.CRITICAL
        assert SpecialistRole.SUPPLY_CHAIN in verdict.specialists

    def test_low_risk_frontend(self):
        verdict = TriageVerdict(
            domains=[Domain.FRONTEND],
            risk=RiskLevel.LOW,
            specialists=[SpecialistRole.FRONTEND_ENGINEER],
            summary="Update dashboard card layout",
        )
        assert verdict.risk == RiskLevel.LOW
        assert len(verdict.specialists) == 1
