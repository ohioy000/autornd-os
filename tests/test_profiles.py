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
