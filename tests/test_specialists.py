"""The specialist roster, which is open the way the domain vocabulary is.

Measured live: asked to staff a firmware signing-key rotation across 40,000
devices, triage returned `infrastructure_engineer` — a role this harness does
not ship. It also returned the domain value `documentation` in the specialists
field. A closed roster cannot express a legal team's paralegal or a marketing
team's copywriter either, so the roster ships defaults rather than limits.
"""

import pytest

from autornd.models.verdicts import SpecialistRole, role_key
from autornd.profiles import ProjectProfile, reset_profile, set_profile
from autornd.specialists.registry import (
    get_specialist,
    get_specialists,
    reload_specialists,
)


@pytest.fixture(autouse=True)
def _clean_profile():
    reset_profile()
    reload_specialists()
    yield
    reset_profile()
    reload_specialists()


class TestShippedRoster:
    def test_a_shipped_role_resolves(self):
        assert get_specialist("hardware_engineer").name == "Hardware Engineer"

    def test_an_enum_member_resolves_the_same_specialist(self):
        assert (get_specialist(SpecialistRole.TEST_ENGINEER)
                is get_specialist("test_engineer"))

    def test_spelling_is_normalised(self):
        assert (get_specialist("Test Engineer")
                is get_specialist("test_engineer"))


class TestUndeclaredRole:
    """A role nobody declared must degrade into a working specialist. Raising
    would fail an entire workflow over a role name, and dropping it would throw
    away the judgement triage actually made."""

    def test_it_does_not_raise(self):
        spec = get_specialist("infrastructure_engineer")
        assert spec.name == "Infrastructure Engineer"

    def test_it_gets_a_usable_tier_and_prompt(self):
        spec = get_specialist("bioprocess_scientist")
        assert spec.router_function == "engineering"
        assert "Bioprocess Scientist" in spec.system_prompt
        # the output contract must reach it too, or it answers that it has no
        # filesystem and validate reads that as a failed implementation
        assert "no repository" in spec.system_prompt

    def test_it_is_stable_across_calls(self):
        assert get_specialist("copywriter") is get_specialist("copywriter")

    def test_a_mixed_roster_resolves_in_one_call(self):
        team = get_specialists(["paralegal", SpecialistRole.TEST_ENGINEER])
        assert [s.name for s in team] == ["Paralegal", "Test Engineer"]


class TestProfileDeclaredRole:
    def test_a_declared_role_carries_its_own_grounding(self):
        set_profile(ProjectProfile(
            name="Chambers", description="A legal practice",
            roles={"paralegal": {
                "name": "Paralegal",
                "domain": "Records retention, statutory schedules",
                "tier": "engineering",
                "expertise": "Your domain: statutory retention schedules.",
            }},
        ))
        reload_specialists()
        spec = get_specialist("paralegal")
        assert spec.name == "Paralegal"
        assert "statutory retention schedules" in spec.system_prompt
        # and it is built by the same path, so it inherits project context
        assert "A legal practice" in spec.system_prompt
        assert "no repository" in spec.system_prompt

    def test_a_declared_role_can_choose_its_tier(self):
        set_profile(ProjectProfile(name="T", roles={
            "counsel": {"name": "Counsel", "tier": "architecture"}}))
        reload_specialists()
        assert get_specialist("counsel").router_function == "architecture"

    def test_a_profile_can_refine_a_shipped_role(self):
        set_profile(ProjectProfile(name="T", roles={
            "test_engineer": {"name": "Validation Lead",
                              "expertise": "Your domain: protocol validation."}}))
        reload_specialists()
        spec = get_specialist("test_engineer")
        assert spec.name == "Validation Lead"
        assert "protocol validation" in spec.system_prompt

    def test_reload_forgets_a_previous_profile(self):
        set_profile(ProjectProfile(name="T", roles={
            "paralegal": {"name": "Paralegal"}}))
        reload_specialists()
        assert get_specialist("paralegal").name == "Paralegal"
        reset_profile()
        reload_specialists()
        # still resolvable, but now as a generalist rather than a declared role
        assert get_specialist("paralegal").name == "Paralegal"
        assert role_key("paralegal") == "paralegal"
