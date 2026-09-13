"""Test project profile system."""

import pytest

from autornd.profiles import (
    DEFAULT_PROFILE,
    ProjectProfile,
    get_profile,
    list_profiles,
    load_profile,
    reset_profile,
    set_profile,
)


class TestProjectProfile:
    def test_default_profile_has_name(self):
        assert DEFAULT_PROFILE.name == "AutoRnD"

    def test_default_profile_empty_context(self):
        assert DEFAULT_PROFILE.build_context() == ""

    def test_build_context_with_stack(self):
        p = ProjectProfile(
            name="TestProject",
            description="A test project",
            stack=["Python", "React"],
            constraints=["4GB RAM"],
        )
        ctx = p.build_context()
        assert "TestProject: A test project" in ctx
        assert "Python" in ctx
        assert "React" in ctx
        assert "4GB RAM" in ctx

    def test_build_context_name_only(self):
        p = ProjectProfile(name="Bare", description="Minimal", stack=["Go"])
        ctx = p.build_context()
        assert "Bare: Minimal" in ctx
        assert "Go" in ctx

    def test_get_specialist_context_defined(self):
        p = ProjectProfile(
            specialists={"firmware_engineer": {"context": "ESP32 targets"}}
        )
        assert p.get_specialist_context("firmware_engineer") == "ESP32 targets"

    def test_get_specialist_context_undefined(self):
        p = ProjectProfile()
        assert p.get_specialist_context("firmware_engineer") is None

    def test_get_docs_dir(self):
        p = ProjectProfile(name="SmartFactory")
        assert p.get_docs_dir() == "smartfactory"

    def test_get_docs_dir_with_spaces(self):
        p = ProjectProfile(name="My Project")
        assert p.get_docs_dir() == "my_project"


class TestProfileLoading:
    def test_load_example_profile(self):
        p = load_profile("example")
        assert p.name == "SmartFactory"
        assert len(p.stack) > 0
        assert len(p.constraints) > 0

    def test_load_example_has_specialist_overrides(self):
        p = load_profile("example")
        ctx = p.get_specialist_context("firmware_engineer")
        assert ctx is not None
        assert "Raspberry Pi" in ctx

    def test_load_missing_profile_raises(self):
        with pytest.raises(FileNotFoundError):
            load_profile("nonexistent_profile_xyz")

    def test_list_profiles_finds_example(self):
        profiles = list_profiles()
        assert "example" in profiles

    def test_example_build_context(self):
        p = load_profile("example")
        ctx = p.build_context()
        assert "SmartFactory" in ctx
        assert "Modbus" in ctx or "Raspberry" in ctx


class TestProfileSingleton:
    def setup_method(self):
        reset_profile()

    def teardown_method(self):
        reset_profile()

    def test_get_profile_returns_default(self):
        p = get_profile()
        assert p.name == "AutoRnD"

    def test_set_profile_overrides(self):
        custom = ProjectProfile(name="Custom")
        set_profile(custom)
        assert get_profile().name == "Custom"

    def test_reset_clears_cache(self):
        set_profile(ProjectProfile(name="Temp"))
        reset_profile()
        p = get_profile()
        assert p.name == "AutoRnD"


class TestProfileVocabularies:
    """Domains and roles are both declared by the project, because no shipped
    list covers civil engineering, food safety or a paralegal."""

    def test_a_domain_may_be_a_bare_lead(self):
        profile = ProjectProfile(name="T", domains={"mechanical": "hardware_engineer"})
        assert profile.get_domain_lead("mechanical") == "hardware_engineer"
        assert profile.get_domain_checks("mechanical") == ()

    def test_a_domain_may_carry_its_own_checks(self):
        profile = ProjectProfile(name="T", domains={"legal_ops": {
            "lead": "paralegal",
            "checks": ["Is every retention period tied to a named statute?"],
        }})
        assert profile.get_domain_lead("legal_ops") == "paralegal"
        assert profile.get_domain_checks("legal_ops") == (
            "Is every retention period tied to a named statute?",)

    def test_a_single_check_may_be_a_string(self):
        profile = ProjectProfile(name="T", domains={
            "legal_ops": {"lead": "paralegal", "checks": "One question?"}})
        assert profile.get_domain_checks("legal_ops") == ("One question?",)

    def test_domain_spelling_is_normalised(self):
        profile = ProjectProfile(name="T", domains={"Food Safety": "supply_chain"})
        assert profile.get_domain_lead("food_safety") == "supply_chain"
        assert profile.domain_vocabulary() == ["food_safety"]

    def test_roles_are_declared_and_normalised(self):
        profile = ProjectProfile(name="T", roles={
            "Paralegal": {"name": "Paralegal", "tier": "engineering"}})
        assert profile.role_vocabulary() == ["paralegal"]
        assert profile.get_role("paralegal")["tier"] == "engineering"

    def test_an_undeclared_role_is_none(self):
        assert ProjectProfile(name="T").get_role("paralegal") is None

    def test_a_profile_file_loads_both(self, tmp_path, monkeypatch):
        import autornd.profiles as profiles_module

        (tmp_path / "wide.yaml").write_text(
            "name: Wide\n"
            "domains:\n"
            "  legal_ops:\n"
            "    lead: paralegal\n"
            "    checks:\n"
            "      - Is every retention period tied to a named statute?\n"
            "roles:\n"
            "  paralegal:\n"
            "    name: Paralegal\n"
            "    tier: engineering\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(profiles_module, "PROFILES_DIR", tmp_path)
        profile = profiles_module.load_profile("wide")
        assert profile.get_domain_lead("legal_ops") == "paralegal"
        assert len(profile.get_domain_checks("legal_ops")) == 1
        assert profile.get_role("paralegal")["name"] == "Paralegal"
