"""B14: the two structural role slots are the profile's, not the harness's.

**The measurement this closes.** Two rules in this codebase are not judgement
calls and so are enforced in code: risky work is checked by someone, and work
spanning domains has someone holding the system-level view. Until B14 the roles
filling those slots were the shipped engineering ones, hardcoded at four sites.
They bound on every profile — measured at §24.1(d), **77 of 108 wide-suite units
were assigned a test engineer in BOTH arms of a studio/control comparison,
identical, because the injection never consulted the profile.**

The rules are unchanged here. Only their operands moved.

Two invariants, and the first matters most: **a profile that declares nothing
behaves exactly as it did before B14.** The generalization must be invisible to
every engineering project, or it is a regression wearing a feature's clothes.
"""

from __future__ import annotations

import pytest

from autornd.engine.review_composition import get_review_team
from autornd.engine.phases import enforce_triage_composition
from autornd.models.verdicts import RiskLevel, SpecialistRole, TriageVerdict, role_key
from autornd.profiles import DEFAULT_PROFILE, ProjectProfile, set_profile

TESTER = role_key(SpecialistRole.TEST_ENGINEER)
ARCHITECT = role_key(SpecialistRole.SYSTEMS_ARCHITECT)


@pytest.fixture(autouse=True)
def _restore_profile():
    yield
    set_profile(DEFAULT_PROFILE)


def _studio() -> ProjectProfile:
    return ProjectProfile(
        name="Studio",
        structural_roles={"checks_work": "editor",
                          "holds_system_view": "strategist"},
    )


def _triage(risk=RiskLevel.HIGH, domains=("backend",), specialists=()):
    return TriageVerdict(domains=list(domains), risk=risk,
                         specialists=list(specialists), summary="s")


class TestAnUndeclaredProfileIsUnchanged:
    """The regression guard. Everything below must read as it did pre-B14."""

    def test_the_defaults_are_the_shipped_engineering_roles(self):
        assert DEFAULT_PROFILE.role_that_checks_work() == TESTER
        assert DEFAULT_PROFILE.role_that_holds_system_view() == ARCHITECT

    def test_triage_still_gets_a_test_engineer_at_high_risk(self):
        set_profile(DEFAULT_PROFILE)
        v = _triage(risk=RiskLevel.HIGH)
        enforce_triage_composition(v)
        assert TESTER in [role_key(s) for s in v.specialists]

    def test_triage_still_gets_an_architect_on_multiple_domains(self):
        set_profile(DEFAULT_PROFILE)
        v = _triage(risk=RiskLevel.LOW, domains=("backend", "frontend"))
        enforce_triage_composition(v)
        assert ARCHITECT in [role_key(s) for s in v.specialists]

    def test_the_review_team_is_unchanged_at_every_risk(self):
        """Pinned against the pre-B14 rosters, computed by hand from the rules:
        low returns the single most relevant reviewer; medium adds the checker;
        high adds the system view as well."""
        set_profile(DEFAULT_PROFILE)
        assert get_review_team(RiskLevel.LOW, ["backend"], ["backend_engineer"]) \
            == ["backend_engineer"]
        assert get_review_team(RiskLevel.MEDIUM, ["backend"], ["backend_engineer"]) \
            == ["backend_engineer", "test_engineer"]
        assert get_review_team(RiskLevel.HIGH, ["backend"], ["backend_engineer"]) \
            == ["systems_architect", "backend_engineer", "test_engineer"]

    def test_an_empty_structural_roles_map_is_the_same_as_none(self):
        set_profile(ProjectProfile(name="Bare", structural_roles={}))
        bare = get_review_team(RiskLevel.HIGH, ["backend"], ["backend_engineer"])
        set_profile(DEFAULT_PROFILE)
        assert bare == get_review_team(RiskLevel.HIGH, ["backend"], ["backend_engineer"])
        assert TESTER in bare and ARCHITECT in bare


class TestADeclaredProfileGetsItsOwnRoles:
    """The feature. A content studio's work is checked by an editor."""

    def test_the_accessors_return_the_declared_roles(self):
        p = _studio()
        assert p.role_that_checks_work() == "editor"
        assert p.role_that_holds_system_view() == "strategist"

    def test_triage_injects_the_declared_checker_not_a_test_engineer(self):
        set_profile(_studio())
        v = _triage(risk=RiskLevel.CRITICAL)
        enforce_triage_composition(v)
        keys = [role_key(s) for s in v.specialists]
        assert "editor" in keys
        assert TESTER not in keys, (
            "the hardcoded engineering role bound on a profile that declared its own")

    def test_triage_injects_the_declared_system_view_not_an_architect(self):
        set_profile(_studio())
        v = _triage(risk=RiskLevel.LOW, domains=("copywriting", "seo_analytics"))
        enforce_triage_composition(v)
        keys = [role_key(s) for s in v.specialists]
        assert "strategist" in keys and ARCHITECT not in keys

    def test_the_review_team_carries_the_declared_roles(self):
        set_profile(_studio())
        team = get_review_team(RiskLevel.HIGH, ["copywriting"], ["copywriter"])
        assert "editor" in team and "strategist" in team
        assert TESTER not in team and ARCHITECT not in team, (
            "a content brief was reviewed by an engineering roster")

    def test_the_low_risk_fallback_uses_the_declared_system_view(self):
        """`[lead or ARCHITECT]` was the fourth reach, and the one outside the
        line range the record cited for this site."""
        set_profile(_studio())
        assert get_review_team(RiskLevel.LOW, [], []) == ["strategist"]


class TestPartialDeclaration:
    def test_declaring_one_slot_leaves_the_other_at_its_default(self):
        set_profile(ProjectProfile(name="Half",
                                   structural_roles={"checks_work": "editor"}))
        team = get_review_team(RiskLevel.HIGH, ["backend"], ["backend_engineer"])
        assert "editor" in team and ARCHITECT in team and TESTER not in team


class TestThePydanticBypassIsGone:
    """Recorded unfixed since §26 and deferred to this change: the injection
    appended an enum member to a `list[str]` after construction, so the verdict
    held a mixed list."""

    def test_every_injected_specialist_is_a_plain_string(self):
        set_profile(DEFAULT_PROFILE)
        v = _triage(risk=RiskLevel.CRITICAL, domains=("backend", "frontend"))
        enforce_triage_composition(v)
        assert v.specialists, "nothing was injected, so this proves nothing"
        for s in v.specialists:
            assert type(s) is str, f"{s!r} is {type(s).__name__}, not str"

    def test_injection_is_idempotent(self):
        set_profile(DEFAULT_PROFILE)
        v = _triage(risk=RiskLevel.HIGH, domains=("backend", "frontend"))
        enforce_triage_composition(v)
        first = list(v.specialists)
        enforce_triage_composition(v)
        assert v.specialists == first, "a second pass duplicated a structural role"
