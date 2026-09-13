"""Risk-based review team composition per the architecture doc.

Maps (risk_level, domains) to the correct specialist set for review,
enforcing the exact compositions from the risk taxonomy table.
"""

from __future__ import annotations

from autornd.models.verdicts import Domain, RiskLevel, SpecialistRole, domain_key


def get_review_team(
    risk: RiskLevel, domains: list[object]
) -> list[SpecialistRole]:
    """Who reviews, given the risk level and the domains in play.

    Domains arrive as normalised strings and may name a subject this harness
    has never seen — R&D spans more than any shipped list. An unrecognised
    domain is not ignored: at medium and above it pulls in the architect and a
    test engineer, because unfamiliar work is exactly what wants a generalist
    and someone to check it.
    """
    keys = {domain_key(d) for d in domains}
    known = {domain_key(d) for d in Domain}
    unrecognised = bool(keys - known)

    if risk == RiskLevel.CRITICAL:
        return list(SpecialistRole)

    def ordered(team: set[SpecialistRole]) -> list[SpecialistRole]:
        return sorted(team, key=lambda r: list(SpecialistRole).index(r))

    if risk == RiskLevel.HIGH:
        team: set[SpecialistRole] = {
            SpecialistRole.SYSTEMS_ARCHITECT,
            SpecialistRole.TEST_ENGINEER,
        }
        if {"hardware", "supply_chain"} & keys:
            team.add(SpecialistRole.HARDWARE_ENGINEER)
            team.add(SpecialistRole.SUPPLY_CHAIN)
        if "firmware" in keys:
            team.add(SpecialistRole.FIRMWARE_ENGINEER)
        return ordered(team)

    if risk == RiskLevel.MEDIUM:
        team = set()
        if {"backend", "infrastructure"} & keys:
            team.add(SpecialistRole.BACKEND_ENGINEER)
        if "infrastructure" in keys:
            team.add(SpecialistRole.SYSTEMS_ARCHITECT)
        if "backend" in keys:
            team.add(SpecialistRole.TEST_ENGINEER)
        if "firmware" in keys:
            team.add(SpecialistRole.FIRMWARE_ENGINEER)
            team.add(SpecialistRole.TEST_ENGINEER)
        if "hardware" in keys:
            team.add(SpecialistRole.HARDWARE_ENGINEER)
            team.add(SpecialistRole.TEST_ENGINEER)
        if unrecognised:
            team.add(SpecialistRole.SYSTEMS_ARCHITECT)
            team.add(SpecialistRole.TEST_ENGINEER)
        if not team:
            team.add(SpecialistRole.BACKEND_ENGINEER)
            team.add(SpecialistRole.TEST_ENGINEER)
        return ordered(team)

    # Low risk
    if "frontend" in keys:
        return [SpecialistRole.FRONTEND_ENGINEER]
    return [SpecialistRole.SYSTEMS_ARCHITECT]
