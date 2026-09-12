"""Risk-based review team composition per the architecture doc.

Maps (risk_level, domains) to the correct specialist set for review,
enforcing the exact compositions from the risk taxonomy table.
"""

from __future__ import annotations

from autornd.models.verdicts import Domain, RiskLevel, SpecialistRole


def get_review_team(
    risk: RiskLevel, domains: list[Domain]
) -> list[SpecialistRole]:
    if risk == RiskLevel.CRITICAL:
        return list(SpecialistRole)

    if risk == RiskLevel.HIGH:
        team: set[SpecialistRole] = {
            SpecialistRole.SYSTEMS_ARCHITECT,
            SpecialistRole.TEST_ENGINEER,
        }
        if Domain.HARDWARE in domains or Domain.SUPPLY_CHAIN in domains:
            team.add(SpecialistRole.HARDWARE_ENGINEER)
            team.add(SpecialistRole.SUPPLY_CHAIN)
        if Domain.FIRMWARE in domains:
            team.add(SpecialistRole.FIRMWARE_ENGINEER)
        return sorted(team, key=lambda r: list(SpecialistRole).index(r))

    if risk == RiskLevel.MEDIUM:
        team = set[SpecialistRole]()
        if Domain.BACKEND in domains or Domain.INFRASTRUCTURE in domains:
            team.add(SpecialistRole.BACKEND_ENGINEER)
        if Domain.INFRASTRUCTURE in domains:
            team.add(SpecialistRole.SYSTEMS_ARCHITECT)
        if Domain.BACKEND in domains:
            team.add(SpecialistRole.TEST_ENGINEER)
        if Domain.FIRMWARE in domains:
            team.add(SpecialistRole.FIRMWARE_ENGINEER)
            team.add(SpecialistRole.TEST_ENGINEER)
        if Domain.HARDWARE in domains:
            team.add(SpecialistRole.HARDWARE_ENGINEER)
            team.add(SpecialistRole.TEST_ENGINEER)
        if not team:
            team.add(SpecialistRole.BACKEND_ENGINEER)
            team.add(SpecialistRole.TEST_ENGINEER)
        return sorted(team, key=lambda r: list(SpecialistRole).index(r))

    # Low risk
    if Domain.FRONTEND in domains:
        return [SpecialistRole.FRONTEND_ENGINEER]
    if Domain.DOCUMENTATION in domains:
        return [SpecialistRole.SYSTEMS_ARCHITECT]
    return [SpecialistRole.SYSTEMS_ARCHITECT]
