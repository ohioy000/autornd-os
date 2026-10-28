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

from autornd.models.verdicts import RiskLevel, role_key


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


# Deterministic ordering: the profile's declared order, then anything else
# alphabetically. A review team that reorders between runs makes two
# identical runs look different.
def _ordered(team: set[str]) -> list[str]:
    from autornd.profiles import get_profile

    order = get_profile().ordered_roles()
    shipped = [r for r in order if r in team]
    extra = sorted(team - set(order))
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
