"""The prompt words a profile owns beyond its team: ten framing keys.

The triage risk guide taught with physical-engineering examples, the hazard sentence said "injure a person or damage
equipment" at four sites, the decision switches' questions named "a datasheet", and a request that said "per the
datasheet" demanded a lookup, under every profile. Each is now a profile word, so a field can teach with its own.

The engineering text is cut out of the code word for word. The golden prompts of test_profile_framing.py hold what
the models are sent; tests/fixtures/words/main.json holds the two surfaces those goldens do not reach, the questions
the decision switches put and the answers of the citation-phrase detector, captured from main (828d033) before the
words were keys. Under engineering and every profile built on it nothing a model reads, and nothing a free check
decides, has changed. Each word is also read where the text used to be written, shown with a marker no shipped
profile contains.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from autornd.config import settings
from autornd.knowledge.context import request_demands_sources, reset_rerank_mode
from autornd.models.verdicts import EscalationVerdict
from autornd.profiles import _general, framing, list_profiles, load_profile, set_profile
from autornd.routing.switches import fill_switch_words
from autornd.specialists.registry import reload_specialists
from tests.prompt_capture import capture_all, switch_requests

ROOT = Path(__file__).resolve().parent.parent
MAIN = json.loads((ROOT / "tests" / "fixtures" / "words" / "main.json").read_text(encoding="utf-8"))
ENGINEERING_FAMILY = ("engineering", "example", "cupline", "tier4")

RISK_WORDS = ("risk_harm_rules", "risk_paper_examples", "risk_high_examples",
              "risk_medium_examples", "risk_protective_example")
SWITCH_WORDS = ("switch_outside_sources", "switch_computed_values", "switch_published_documents")
TEN = RISK_WORDS + ("hazard_harm",) + SWITCH_WORDS + ("source_request_terms",)

# A value no shipped profile holds, for each word, so a prompt that carries it was built from the active profile.
MARKS = {key: f"<<{key}>>" for key in TEN}
MARKS["source_request_terms"] = "marker phrase alpha\n  Marker Phrase BETA  \n\n"


def _use(name: str) -> None:
    set_profile(load_profile(name))
    reload_specialists()


def _use_marked(**marks: str) -> None:
    """Engineering's team and words, with these words replaced."""
    base = load_profile("engineering")
    set_profile(replace(base, framing={**base.framing, **marks}))
    reload_specialists()


async def _capture(monkeypatch) -> dict[str, dict[str, str]]:
    monkeypatch.setattr(settings, "model_research", "test-provider/test-research")
    monkeypatch.setattr(settings, "model_ranker", "test-provider/test-rank")
    reset_rerank_mode()
    return await capture_all()


class TestTheTenWordsEveryProfileResolves:
    def test_general_declares_thirty_five_words_and_the_ten_are_among_them(self):
        """Nineteen team words, the ten here, and the six of the escalation prompt (test_profile_escalation_words.py)."""
        declared = set(_general().framing)
        assert len(declared) == 35
        assert set(TEN) <= declared

    def test_no_profile_declares_a_word_general_does_not(self):
        """framing() takes its key set from general: a word only another profile has is never read."""
        declared = set(_general().framing)
        for name in list_profiles():
            assert set(load_profile(name).framing) <= declared, name

    def test_every_profile_resolves_every_word_and_the_passages_are_not_blank(self):
        for name in list_profiles():
            _use(name)
            words = framing()
            assert set(TEN) <= set(words), name
            for key in TEN:
                assert isinstance(words[key], str), (name, key)
                if key != "source_request_terms":
                    assert words[key].strip(), f"{name} has a blank {key}"


class TestEveryWordIsReadWhereTheTextWasWritten:
    async def test_the_risk_guide_takes_each_passage_at_its_own_line(self, monkeypatch):
        _use_marked(**{key: MARKS[key] for key in RISK_WORDS})
        guide = (await _capture(monkeypatch))["triage"]["user"]
        assert "rule that exists to prevent harm — <<risk_harm_rules>>? If so it is critical," in guide
        assert "at every stage. <<risk_paper_examples>>\n\nNot every published standard" in guide
        assert "- high: <<risk_high_examples>>\n- medium: <<risk_medium_examples>>\n- low:" in guide
        assert "not by the stage it is at. <<risk_protective_example>>\n\nA protocol, schedule" in guide
        for key in RISK_WORDS:
            assert guide.count(MARKS[key]) == 1, key

    async def test_no_engineering_example_is_left_in_the_guide_of_a_profile_with_its_own(self, monkeypatch):
        _use_marked(**{key: MARKS[key] for key in RISK_WORDS})
        guide = (await _capture(monkeypatch))["triage"]["user"]
        for old in ("lintel", "pressure vessels", "structural loading", "load path",
                    "aeration", "wiring, installing", "selecting a component"):
            assert old not in guide, old

    async def test_the_hazard_word_is_read_at_every_site_that_defines_a_hazard(self, monkeypatch):
        _use_marked(hazard_harm=MARKS["hazard_harm"])
        captured = await _capture(monkeypatch)
        sites = ("domain_review", "validate", "review_collaborative", "review_adversarial", "doublecheck")
        for site in sites:
            user = captured[site]["user"]
            assert "followed as written, <<hazard_harm>>" in user, site
            assert "injure a person" not in user, site

    def test_no_hazard_sentence_is_written_into_the_code(self):
        """A fifth prompt that wrote it out would teach hazard in engineering's words under every profile."""
        phases = (ROOT / "autornd" / "engine" / "phases.py").read_text(encoding="utf-8")
        assert phases.count("{f['hazard_harm']}") == 4
        found = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "autornd").rglob("*.py"))
                 if "damage equipment" in p.read_text(encoding="utf-8")]
        assert not found, f"a hazard definition is written into the code: {found}"


class TestTheSwitchQuestions:
    async def test_the_engineering_family_sends_what_main_sent(self):
        for name in ENGINEERING_FAMILY:
            _use(name)
            assert await switch_requests() == MAIN["switches"], name

    async def test_a_profiles_own_words_are_filled_into_the_questions(self):
        _use_marked(**{key: MARKS[key] for key in SWITCH_WORDS})
        sent = await switch_requests()
        assert sent["needs_sources"]["instructions"].endswith(
            "from an outside source, such as <<switch_outside_sources>>?")
        assert sent["needs_calculation"]["criteria"]["true"].endswith(
            "such as <<switch_computed_values>>.")
        assert sent["needs_calculation"]["criteria"]["false"] == (
            "It asks what <<switch_published_documents>> states.")
        assert "datasheet" not in json.dumps(sent)

    async def test_every_switch_is_filled_under_every_profile(self):
        for name in list_profiles():
            _use(name)
            for switch, request in (await switch_requests()).items():
                text = " ".join([request["instructions"], request["criteria"]["true"],
                                 request["criteria"]["false"]])
                assert "{" not in text and "}" not in text, (name, switch, text)

    def test_the_fill_leaves_what_is_not_a_switch_word_as_written(self):
        _use_marked(switch_outside_sources="a\n  filing,   a docket")
        assert fill_switch_words("Is it {switch_outside_sources}?") == "Is it a filing, a docket?"
        assert fill_switch_words("{switch_not_declared} and {work} and {x}") == (
            "{switch_not_declared} and {work} and {x}")
        assert fill_switch_words("no braces at all") == "no braces at all"

    async def test_the_words_follow_a_profile_switched_at_run_time(self):
        _use_marked(switch_outside_sources="a marker word")
        assert "such as a marker word?" in (await switch_requests())["needs_sources"]["instructions"]
        _use("engineering")
        assert "such as a standard, a regulation, a datasheet" in (
            await switch_requests())["needs_sources"]["instructions"]


class TestTheCitationPhrases:
    def test_the_engineering_family_answers_as_main_did(self):
        for name in ENGINEERING_FAMILY:
            _use(name)
            got = {request: request_demands_sources(request) for request in MAIN["source_demand"]}
            assert got == MAIN["source_demand"], name

    def test_a_profiles_own_phrases_are_added_to_the_generic_ones(self):
        _use_marked(source_request_terms=MARKS["source_request_terms"])
        assert request_demands_sources("Do it, MARKER phrase ALPHA, please.")
        assert request_demands_sources("marker phrase beta")
        assert request_demands_sources("Answer with sources.")
        assert not request_demands_sources("What is the limit per the datasheet?")

    def test_a_blank_line_is_no_phrase(self):
        """The empty string is inside every text: one stray blank line would demand a lookup of every request."""
        _use_marked(source_request_terms="\n   \n\t\n")
        assert not request_demands_sources("Draft a retention schedule for patient records.")
        assert not request_demands_sources("")

    def test_the_phrases_follow_a_profile_switched_at_run_time(self):
        _use("engineering")
        assert request_demands_sources("What is the limit per the datasheet?")
        _use_marked(source_request_terms="marker phrase alpha")
        assert not request_demands_sources("What is the limit per the datasheet?")
        assert request_demands_sources("marker phrase alpha")
        _use("engineering")
        assert request_demands_sources("What is the limit per the datasheet?")


class TestTheEscalationFieldText:
    def test_requires_human_says_what_the_escalation_prompt_says(self):
        """No model reads this description (nothing sends a schema), but it is the field's documentation and
        named manual hardware intervention, an engineering word, for every profile. It says what the prompt says
        in engineering's words, the ones the prompt was written with."""
        from autornd.engine.phases import escalation_system_prompt

        _use("engineering")
        prompt = " ".join(escalation_system_prompt(1).split())
        tail = re.search(r"Set requires_human to true ONLY if (.*)$", prompt).group(1)
        description = EscalationVerdict.model_fields["requires_human"].description
        assert description == f"True ONLY if {tail}"
        assert "hardware" not in description
