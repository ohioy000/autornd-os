"""Per-profile model pins (PROFILE_MODELS): the grammar, the setting, and the overlay.

A tier named one model for every profile, so a legal team and an engineering team drafted on the
same engineering-tier model. PROFILE_MODELS gives one profile its own model, and optionally its own
provider, for one tier (autornd/routing/pins.py). The owner's direction of 2026-11-21: choosing the
models is as much of the harness as the code, so a profile may have its own.

The overlay is only safe if it is invisible when unused, so this file holds three things apart:
the line is read exactly as written or refused by name; with the setting empty every profile, tier
and accessor resolves as it did before the setting existed; and a pin reaches the profile it names
and no other, `base:` included. Each guarded line was proven by breaking it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autornd import config, profiles
from autornd.config import PINNABLE_TIERS, ProfilePin, Settings, parse_profile_models, settings
from autornd.routing import pins


def _use(monkeypatch, name: str) -> None:
    """Make a shipped profile the active one for this test only."""
    monkeypatch.setattr(profiles, "_active_profile", profiles._active_profile)
    profiles.set_profile(profiles.load_profile(name))


class TestTheLineIsReadAsWrittenOrRefusedByName:
    def test_an_empty_line_pins_nothing(self):
        assert parse_profile_models("") == {}
        assert parse_profile_models("   ") == {}
        assert parse_profile_models(" , ,") == {}

    def test_a_pin_with_a_provider(self):
        got = parse_profile_models("legal:engineering=vendor/legal-model@vendor")
        assert got == {"legal": {"engineering": ProfilePin("vendor/legal-model", "vendor")}}

    def test_a_pin_without_a_provider_names_none(self):
        got = parse_profile_models("legal:engineering=vendor/legal-model")
        assert got["legal"]["engineering"] == ProfilePin("vendor/legal-model", "")

    def test_a_variant_suffix_is_part_of_the_model(self):
        got = parse_profile_models("legal:engineering=vendor/model:free@acme")
        assert got["legal"]["engineering"] == ProfilePin("vendor/model:free", "acme")

    def test_several_entries_with_spaces(self):
        got = parse_profile_models(
            " legal:engineering=a/b@p , legal:triage=c/d , finance:research=e/f@q ")
        assert got == {
            "legal": {"engineering": ProfilePin("a/b", "p"), "triage": ProfilePin("c/d", "")},
            "finance": {"research": ProfilePin("e/f", "q")},
        }

    def test_a_tier_is_folded_to_lower_case_and_a_profile_is_not(self):
        got = parse_profile_models("Legal:ENGINEERING=a/b")
        assert got == {"Legal": {"engineering": ProfilePin("a/b", "")}}

    @pytest.mark.parametrize("line, why", [
        ("legal:engineering", "has no '='"),
        ("legal=vendor/m", "does not start with <profile>:<tier>"),
        (":engineering=vendor/m", "does not start with <profile>:<tier>"),
        ("legal:=vendor/m", "does not start with <profile>:<tier>"),
        ("le gal:engineering=vendor/m", "is not a profile file name"),
        ("legal:independent=vendor/m", "follows from the premium and architecture tiers"),
        ("legal:planner=vendor/m", "is not a tier a profile can pin"),
        ("legal:engineering=notamodel", "must look like vendor/name"),
        ("legal:engineering=vendor/ model", "must look like vendor/name"),
        ("legal:engineering=", "must look like vendor/name"),
        ("legal:engineering=vendor/m@", "ends in '@' with no provider"),
        ("legal:engineering=vendor/m@a@b", "has more than one '@'"),
        ("legal:engineering=vendor/m@a b", "has a space in it"),
        ("legal:engineering=a/b,legal:engineering=c/d", "'legal:engineering' is pinned twice"),
    ])
    def test_a_malformed_entry_is_refused_and_named(self, line, why):
        with pytest.raises(ValueError) as refused:
            parse_profile_models(line)
        assert why in str(refused.value)
        # the sentence names the entry, so the owner can find it in a long line
        assert line.split(",")[-1].strip().split("=")[0] in str(refused.value) or "pinned twice" in why

    def test_every_tier_a_setting_names_is_pinnable_and_no_other_is(self):
        """A new tier setting that no profile can pin is a seat the overlay misses."""
        named = {f.removeprefix("model_") for f in Settings.model_fields if f.startswith("model_")}
        assert len(named) == 12, "the tiers a setting names were not found; the guard read nothing"
        assert set(PINNABLE_TIERS) == named
        assert "independent" not in PINNABLE_TIERS


class TestTheSettingRefusesAMalformedLine:
    def test_the_setting_takes_a_good_line(self):
        cfg = Settings(profile_models="legal:engineering=vendor/legal-model@vendor")
        assert cfg.profile_models == "legal:engineering=vendor/legal-model@vendor"

    def test_the_setting_refuses_a_bad_line(self):
        with pytest.raises(ValidationError):
            Settings(profile_models="garbage")

    def test_start_up_stops_with_a_plain_sentence_not_a_traceback(self, monkeypatch):
        monkeypatch.setenv("PROFILE_MODELS", "legal:engineering=notamodel")
        with pytest.raises(SystemExit) as stopped:
            config._build_settings()
        text = str(stopped.value)
        assert "PROFILE_MODELS is malformed" in text
        assert "legal:engineering=notamodel" in text
        assert "<profile>:<tier>=<model-id>[@<provider>]" in text
        assert "Traceback" not in text and "ValidationError" not in text

    def test_a_malformed_tier_still_reports_as_a_tier(self, monkeypatch):
        """The new refusal must not swallow the one that was there."""
        monkeypatch.setenv("MODEL_TRIAGE", "nomodel")
        with pytest.raises(SystemExit) as stopped:
            config._build_settings()
        assert "MODEL_TRIAGE" in str(stopped.value)
        assert "PROFILE_MODELS" not in str(stopped.value)

    def test_a_pin_is_not_a_runtime_setting(self):
        """A pin names who answers and is paid: the owner's line in .env, not a PUT."""
        assert settings.RUNTIME_MUTABLE, "the runtime list was not read; the guard saw nothing"
        assert "profile_models" not in settings.RUNTIME_MUTABLE

    def test_the_suite_forces_the_setting_empty(self):
        import tests.conftest as conftest

        assert conftest.PLACEHOLDERS["PROFILE_MODELS"] == ""
        assert settings.profile_models == ""


class TestAProfileKnowsItsFile:
    def test_the_stem_is_the_file_and_not_the_display_name(self):
        assert profiles.load_profile("studio").stem == "studio"
        assert profiles.load_profile("studio").name != "studio"
        assert profiles.load_profile("engineering").stem == "engineering"
        assert profiles.DEFAULT_PROFILE.stem == "general"

    def test_a_profile_built_on_another_keeps_its_own_stem(self):
        for name in ("example", "cupline", "tier4"):
            assert profiles.load_profile(name).stem == name

    def test_a_profile_built_in_code_has_no_stem(self):
        assert profiles.ProjectProfile().stem == ""


class TestAnEmptySettingChangesNothing:
    @pytest.mark.parametrize("stem", profiles.list_profiles())
    def test_no_tier_of_any_shipped_profile_resolves_to_a_pin(self, monkeypatch, stem):
        monkeypatch.setattr(settings, "profile_models", "")
        _use(monkeypatch, stem)
        assert pins.pins_by_profile() == {}
        for tier in PINNABLE_TIERS:
            assert pins.active_pin(tier) is None, (stem, tier)
            assert pins.tier_model(tier, "global/model") == "global/model", (stem, tier)
        base = {"engineering": "global/e", "triage": "global/t"}
        assert pins.effective_models(base) == base

    def test_the_shipped_profiles_were_found(self):
        """A guard that read no profile would pass on nothing."""
        assert {"general", "engineering", "example", "studio"} <= set(profiles.list_profiles())


class TestAPinReachesTheProfileItNamesAndNoOther:
    LINE = "legal:engineering=vendor/legal-model@vendor,finance:triage=vendor/cheap-model"

    def _active(self, monkeypatch, stem: str) -> None:
        monkeypatch.setattr(settings, "profile_models", self.LINE)
        monkeypatch.setattr(profiles, "_active_profile", profiles._active_profile)
        profiles.set_profile(profiles.ProjectProfile(stem=stem))

    def test_the_named_profile_reads_its_pin(self, monkeypatch):
        self._active(monkeypatch, "legal")
        assert pins.active_pin("engineering") == ProfilePin("vendor/legal-model", "vendor")
        assert pins.tier_model("engineering", "global/e") == "vendor/legal-model"

    def test_a_tier_it_did_not_pin_stays_global(self, monkeypatch):
        self._active(monkeypatch, "legal")
        assert pins.active_pin("triage") is None
        assert pins.tier_model("triage", "global/t") == "global/t"

    def test_another_profiles_pin_is_not_seen(self, monkeypatch):
        self._active(monkeypatch, "legal")
        assert pins.active_pin("triage") is None        # finance's pin
        self._active(monkeypatch, "finance")
        assert pins.active_pin("triage") == ProfilePin("vendor/cheap-model", "")
        assert pins.active_pin("engineering") is None   # legal's pin

    def test_switching_the_profile_changes_the_next_answer(self, monkeypatch):
        self._active(monkeypatch, "legal")
        assert pins.tier_model("engineering", "g") == "vendor/legal-model"
        profiles.set_profile(profiles.ProjectProfile(stem="finance"))
        assert pins.tier_model("engineering", "g") == "g"

    def test_a_profile_built_in_code_has_no_pins(self, monkeypatch):
        self._active(monkeypatch, "")
        assert all(pins.active_pin(tier) is None for tier in PINNABLE_TIERS)

    def test_a_pin_does_not_inherit_through_base(self, monkeypatch):
        """example, cupline and tier4 are built on engineering; they must not change model
        because engineering gained one."""
        monkeypatch.setattr(settings, "profile_models", "engineering:engineering=vendor/e-model")
        _use(monkeypatch, "engineering")
        assert pins.active_pin("engineering") == ProfilePin("vendor/e-model", "")
        for name in ("example", "cupline", "tier4"):
            profiles.set_profile(profiles.load_profile(name))
            assert pins.active_pin("engineering") is None, name

    def test_a_pin_on_an_unset_optional_tier_adds_it_to_the_map(self, monkeypatch):
        self._active(monkeypatch, "legal")
        monkeypatch.setattr(settings, "profile_models", "legal:ranker=vendor/rank-model")
        base = {"engineering": "global/e"}
        assert pins.effective_models(base) == {"engineering": "global/e",
                                               "ranker": "vendor/rank-model"}

    def test_the_effective_map_lays_the_pin_over_the_global_one(self, monkeypatch):
        self._active(monkeypatch, "legal")
        base = {"engineering": "global/e", "triage": "global/t"}
        assert pins.effective_models(base) == {"engineering": "vendor/legal-model",
                                               "triage": "global/t"}
        assert base == {"engineering": "global/e", "triage": "global/t"}, "the global map was altered"

    def test_a_pin_for_a_profile_with_no_file_is_still_read_by_name(self, monkeypatch):
        """Whether the file exists is preflight's question; the overlay only matches names."""
        monkeypatch.setattr(settings, "profile_models", "nofile:engineering=vendor/x")
        assert pins.pins_for("nofile")["engineering"].model == "vendor/x"
        assert pins.pins_for("general") == {}
