"""Who reviews the work, given the risk level and who was assigned to it.

Composition used to be a fixed table over seven engineering roles and seven
engineering domains, and `critical` returned every role that exists. Measured
across thirty-six sectors that produced seven engineers reviewing a records
retention schedule — expensive and not useful, which is the same failure twice,
since a reviewer with nothing to say costs a call and adds no accuracy.

So the team is derived from the specialists triage actually assigned, and risk
decides how much scrutiny is added on top rather than who exists.
"""

from __future__ import annotations

from autornd.models.verdicts import RiskLevel, SpecialistRole, role_key

# The shipped defaults for the two structural slots. B14 made the slots
# profile-declarable; these remain what an undeclared profile resolves to, so
# an engineering project's review teams are unchanged.
ARCHITECT = role_key(SpecialistRole.SYSTEMS_ARCHITECT)
TESTER = role_key(SpecialistRole.TEST_ENGINEER)


def _slots() -> tuple[str, str]:
    """(who checks the work, who holds the system view) for the active profile.

    Four reaches into the engineering vocabulary used to live in this file —
    two of them outside the range the record cited, which is how a blueprint
    written from that reference would have generalised half the site. They are
    resolved here, once, so there is one place to look.
    """
    from autornd.profiles import get_profile

    profile = get_profile()
    return profile.role_that_checks_work(), profile.role_that_holds_system_view()

# Deterministic ordering: shipped roles in their declared order, then anything
# else alphabetically. A review team that reorders between runs makes two
# identical runs look different.
_SHIPPED_ORDER = [role_key(r) for r in SpecialistRole]


def _ordered(team: set[str]) -> list[str]:
    shipped = [r for r in _SHIPPED_ORDER if r in team]
    extra = sorted(team - set(_SHIPPED_ORDER))
    return shipped + extra


def get_review_team(
    risk: RiskLevel,
    domains: list[object],
    specialists: list[object] | None = None,
) -> list[str]:
    """The review roster, as normalised role names.

    `specialists` is who triage assigned. When it is empty — an older caller, or
    a triage that assigned nobody — the domain leads stand in, so the team is
    never empty and never arbitrary.
    """
    from autornd.engine.phases import lead_for_domain

    assigned = {role_key(s) for s in (specialists or []) if role_key(s)}
    domain_leads = {role_key(lead_for_domain(d)) for d in (domains or [])}
    if not assigned:
        assigned = set(domain_leads)

    tester, architect = _slots()

    if risk == RiskLevel.LOW:
        # One reviewer, and the most relevant one. Low risk means a wrong
        # answer is trivially reversible, so a second opinion buys nothing.
        lead = next((r for r in _ordered(assigned) if r != tester), None)
        return [lead or architect]

    team = set(assigned)
    team.add(tester)          # someone checks the work at every level above low

    if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        team.add(architect)   # and someone holds the system-level view

    if risk == RiskLevel.CRITICAL:
        # Every domain in play gets its declared lead present, even one triage
        # named but did not staff — at this level an unrepresented domain is
        # the gap that matters.
        team |= domain_leads

    if len(team) < 2:
        team.add(architect)

    return _ordered(team)
