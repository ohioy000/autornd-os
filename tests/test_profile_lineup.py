"""The line-up of shipped profiles, and the shape the four professional ones (legal, finance, medical, science) keep.

A profile is the team, the vocabulary, the framing words, the risk examples and the checks of one field; it does not
choose a model (PROFILE_MODELS does, and ships empty). These four are standalone like studio: no `base:`, none of the
engineering team, words or examples. What they share is a shape this file holds:

 - the vocabulary is the profile's own: no domain or role named like a shipped engineering one;
 - every role that can lead (a domain's lead and the role that holds the system view) sits on the engineering tier,
   the tier a pin targets, and the role that checks the work does not, so a workflow that leaves a node to its role
   never has a drafter review its own work;
 - each says in its constraints, which every specialist prompt carries, that its output is a draft for a qualified
   person to review and is not advice;
 - a pin keyed on the file stem reaches the profile and no other.
"""

from __future__ import annotations

import pytest

from autornd.config import settings
from autornd.models.verdicts import Domain, SpecialistRole, domain_key, role_key
from autornd.profiles import list_profiles, load_profile, set_profile
from autornd.routing.pins import tier_model

PROFESSIONAL = ("legal", "finance", "medical", "science")
SHIPPED = ("cupline", "engineering", "example", "finance", "general", "legal", "medical", "science", "studio",
           "tier4")


class TestTheShippedLineUp:
    def test_ten_profiles_are_shipped_and_these_are_they(self):
        assert tuple(list_profiles()) == SHIPPED

    def test_every_shipped_profile_loads(self):
        for name in SHIPPED:
            assert load_profile(name).stem == name


class TestTheProfessionalProfilesAreStandalone:
    def test_none_builds_on_another_and_each_declares_a_team_and_a_vocabulary(self):
        for name in PROFESSIONAL:
            profile = load_profile(name)
            assert profile.base == "", name
            assert len(profile.domains) == 3, name
            assert len(profile.roles) == 5, name
            assert set(profile.structural_roles) == {"checks_work", "holds_system_view"}, name

    def test_every_domain_has_a_lead_that_is_a_declared_role_and_two_questions_to_judge_it_by(self):
        for name in PROFESSIONAL:
            profile = load_profile(name)
            roles = {role_key(r) for r in profile.roles}
            for domain in profile.domains:
                assert role_key(profile.get_domain_lead(domain)) in roles, (name, domain)
                checks = profile.get_domain_checks(domain)
                assert len(checks) == 2, (name, domain)
                assert all(c.endswith("?") for c in checks), (name, domain, checks)

    def test_the_vocabulary_is_the_profiles_own(self):
        shipped_domains = {d.value for d in Domain}
        shipped_roles = {r.value for r in SpecialistRole}
        for name in PROFESSIONAL:
            profile = load_profile(name)
            assert not {domain_key(d) for d in profile.domains} & shipped_domains, name
            assert not {role_key(r) for r in profile.roles} & shipped_roles, name

    def test_every_role_has_a_name_a_domain_a_tier_and_what_it_knows(self):
        for name in PROFESSIONAL:
            for role, definition in load_profile(name).roles.items():
                assert set(definition) == {"name", "domain", "tier", "expertise"}, (name, role)
                assert all(str(v).strip() for v in definition.values()), (name, role)

    def test_every_lead_is_on_the_engineering_tier_and_the_checker_is_not(self):
        for name in PROFESSIONAL:
            profile = load_profile(name)
            leads = {role_key(profile.get_domain_lead(d)) for d in profile.domains}
            leads.add(profile.role_that_holds_system_view())
            tiers = {role_key(r): d["tier"] for r, d in profile.roles.items()}
            assert {tiers[lead] for lead in leads} == {"engineering"}, name
            assert tiers[profile.role_that_checks_work()] == "architecture", name

    def test_the_two_structural_roles_are_declared_roles_and_are_two_people(self):
        for name in PROFESSIONAL:
            profile = load_profile(name)
            roles = {role_key(r) for r in profile.roles}
            checker, viewer = profile.role_that_checks_work(), profile.role_that_holds_system_view()
            assert {checker, viewer} <= roles and checker != viewer, name

    def test_the_constraints_every_specialist_carries_say_the_output_is_a_draft_for_review(self):
        says = {"legal": "is not legal advice", "finance": "is not financial, tax or investment advice",
                "medical": "is not medical advice and is not for patient care",
                "science": "before anything is run or published"}
        for name in PROFESSIONAL:
            first = load_profile(name).constraints[0].lower()
            assert "draft for a qualified" in first and "to review" in first, name
            assert says[name] in first, name
            assert first in load_profile(name).build_context().lower(), name


class TestAPinReachesItsProfileAndNoOther:
    @pytest.mark.parametrize("stem", PROFESSIONAL)
    def test_a_pin_keyed_on_the_stem_is_reached_under_that_profile_only(self, monkeypatch, stem):
        monkeypatch.setattr(settings, "model_engineering", "global/engineering-model")
        monkeypatch.setattr(settings, "profile_models", f"{stem}:engineering=vendor/field-model@vendor")
        for name in SHIPPED:
            set_profile(load_profile(name))
            want = "vendor/field-model" if name == stem else "global/engineering-model"
            assert tier_model("engineering", settings.model_engineering) == want, (stem, name)
