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


class TestDomainChecks:
    """Before profiles could declare checks, `DOMAIN_CHECKS.get(domain, ())`
    returned nothing for every domain outside the seven shipped ones — so most
    real-world work reached validation with no lenses at all."""

    def teardown_method(self):
        from autornd.profiles import reset_profile
        reset_profile()

    def test_a_shipped_domain_uses_its_own_checks(self):
        from autornd.engine.phases import build_domain_checks

        out = build_domain_checks(["hardware"])
        assert "tolerances" in out

    def test_an_unknown_domain_falls_back_to_generic_checks(self):
        from autornd.engine.phases import GENERIC_CHECKS, build_domain_checks

        out = build_domain_checks(["mechanical"])
        assert out, "an unfamiliar domain used to contribute no lenses at all"
        for check in GENERIC_CHECKS:
            assert check in out

    def test_the_unit_lens_is_always_present_for_unknown_domains(self):
        """`14 dBm` ERP where the source meant EIRP is well-formed and 2.15 dB
        wrong, and no deterministic check catches it."""
        from autornd.engine.phases import build_domain_checks

        assert "units" in build_domain_checks(["acoustics"]).lower()

    def test_a_profile_can_declare_its_own(self):
        from autornd.engine.phases import build_domain_checks
        from autornd.profiles import ProjectProfile, set_profile

        set_profile(ProjectProfile(name="T", domains={"legal_ops": {
            "lead": "paralegal",
            "checks": ["Is every retention period tied to a named statute?"]}}))
        out = build_domain_checks(["legal_ops"])
        assert "named statute" in out

    def test_declared_checks_replace_the_generic_fallback(self):
        from autornd.engine.phases import GENERIC_CHECKS, build_domain_checks
        from autornd.profiles import ProjectProfile, set_profile

        set_profile(ProjectProfile(name="T", domains={
            "legal_ops": {"lead": "paralegal", "checks": ["Only this?"]}}))
        out = build_domain_checks(["legal_ops"])
        assert "Only this?" in out
        assert GENERIC_CHECKS[0] not in out

    def test_no_domains_yields_nothing(self):
        from autornd.engine.phases import build_domain_checks

        assert build_domain_checks([]) == ""
