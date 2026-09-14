"""The configuration this repo ships has to work, because it is what people copy.

A profile and a workflow are data files, so nothing else in the suite touches
them: they can be wrong in every way a YAML file can be wrong and 500 passing
tests will not notice. These are cheap and free, and they cover the two files a
new user is most likely to start from and the one built for a measurement
nobody has managed to take yet.
"""

from __future__ import annotations

import pytest

from autornd.graph.spec import load
from autornd.models.verdicts import Domain, SpecialistRole, domain_key, role_key
from autornd.profiles import load_profile, list_profiles


class TestShippedProfilesLoad:
    def test_both_tracked_profiles_are_listed(self):
        available = list_profiles()
        assert "example" in available and "studio" in available

    @pytest.mark.parametrize("name", ["example", "studio"])
    def test_a_shipped_profile_loads(self, name):
        profile = load_profile(name)
        assert profile.name
        assert profile.build_context(), "a profile with no context teaches nothing"


class TestTheExampleTeachesTheOpenVocabulary:
    """§6.5 is the reason these fields exist, and an example that does not use
    them leaves a reader to discover the feature from the source."""

    @pytest.mark.parametrize("name", ["example", "studio"])
    def test_it_declares_domains_and_roles(self, name):
        profile = load_profile(name)
        assert profile.domain_vocabulary(), f"{name} declares no domains"
        assert profile.role_vocabulary(), f"{name} declares no roles"

    @pytest.mark.parametrize("name", ["example", "studio"])
    def test_something_it_declares_is_not_shipped(self, name):
        """Otherwise the example demonstrates the enums, not the escape from them."""
        profile = load_profile(name)
        shipped_domains = {domain_key(d) for d in Domain}
        shipped_roles = {role_key(r) for r in SpecialistRole}

        novel_domains = set(profile.domain_vocabulary()) - shipped_domains
        novel_roles = set(profile.role_vocabulary()) - shipped_roles
        assert novel_domains, f"{name}'s domains are all shipped ones"
        assert novel_roles, f"{name}'s roles are all shipped ones"

    def test_the_studio_profile_is_not_an_engineering_team(self):
        """The 'works for any team' claim needs one example that is not a team
        of engineers. The shipped defaults already cover engineering."""
        profile = load_profile("studio")
        assert set(profile.domain_vocabulary()).isdisjoint({domain_key(d) for d in Domain})
        assert set(profile.role_vocabulary()).isdisjoint({role_key(r) for r in SpecialistRole})

    def test_a_domain_can_carry_its_own_validation_questions(self):
        """Built-in lenses cover the seven shipped domains only, so before this
        existed, work in any other subject reached validate with no lenses."""
        profile = load_profile("studio")
        assert profile.get_domain_checks("copywriting"), (
            "the example should show what checks: is for")
        assert profile.get_domain_lead("brand_strategy") == "strategist", (
            "and the short form, where a domain is just its lead")


class TestADeclaredRoleIsNotAGeneralist:
    """The fallback exists so an undeclared role does not fail a run. A role the
    profile *did* declare must get its own grounding instead."""

    @pytest.fixture
    def studio(self):
        from autornd.profiles import get_profile, set_profile
        from autornd.specialists.registry import reload_specialists

        previous = get_profile()
        set_profile(load_profile("studio"))
        reload_specialists()
        yield
        set_profile(previous)
        reload_specialists()

    def test_a_declared_role_resolves_to_its_own_definition(self, studio):
        from autornd.specialists.registry import get_specialist

        checker = get_specialist("fact_checker")
        assert checker.role == "fact_checker"
        assert checker.name == "Fact Checker"
        assert "primary source" in checker.system_prompt.lower()
        assert "acting as the" not in checker.system_prompt, (
            "that phrasing is the synthesized generalist — the profile declared "
            "this role, so it should have real grounding")

    def test_an_undeclared_role_still_resolves_as_a_generalist(self, studio):
        from autornd.specialists.registry import get_specialist

        nobody = get_specialist("puppeteer")
        assert nobody.role == "puppeteer"
        assert "acting as the" in nobody.system_prompt


class TestTheIndependentCheckProbe:
    """B6: nine full-workflow attempts never legitimately reached the
    independent pass, each stopping somewhere different and mostly for good
    reasons. This shape removes the earlier exits rather than surviving them."""

    @pytest.fixture
    def spec(self):
        return load("workflows/independent-check-probe.yaml")

    def test_it_loads_and_runs_a_single_pass(self, spec):
        assert spec.ids == [
            "triage", "context", "plan", "implement", "validate",
            "review", "review_clean", "independent_check",
        ]

    def test_there_is_no_loop_and_no_escalation(self, spec):
        assert not [n for n in spec.nodes if n.body], "a build loop defeats the point"
        assert not [n for n in spec.nodes if "escalat" in n.id]
        assert not [n for n in spec.nodes if n.id == "feasibility"]

    def test_the_independent_pass_is_still_conditional(self, spec):
        """It must not fire unconditionally just because this probe wants it.
        unrecallable is a separate axis from risk and stays the trigger."""
        node = next(n for n in spec.nodes if n.id == "independent_check")
        assert node.when == "triage.unrecallable"
        assert node.tier == "independent"
        assert node.depends_on == ["review_clean"]

    def test_review_still_gates(self, spec):
        """Reaching the independent pass past a failed review would measure
        something the product never does."""
        gate = next(n for n in spec.nodes if n.id == "review_clean")
        assert gate.condition == "review.ship == true"
        assert gate.on_fail == "blocked"
