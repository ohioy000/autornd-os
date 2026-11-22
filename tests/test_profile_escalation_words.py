"""The escalation prompt's words: six profile words, so a field's autopsy is written in the field's own terms.

The escalation prompt, read when a loop has failed every attempt it was given, was written for a software team: it
opened "You are the Principal Systems Architect for AutoRnD", spoke of the Implementation agent and of an
architectural flaw, and read an "Architect's Plan", under every profile. Who writes the autopsy, who it directs, the
flaw and the correction it looks for, the scope past which it may ask for a person, and the label of the plan it reads
are now profile words (escalation_*). Only names and labels moved; what the prompt asks for, and when it may ask for
a person, are the same for every profile, and the verdict's fields (typed, read by the loop) are unchanged.

The engineering family's text is cut out of the code word for word: tests/fixtures/words/escalation_main.json holds
main's prompt (828d033, before the words were keys), and the four golden prompt fixtures of test_profile_framing.py
hold what the models are sent. What every other profile is sent is pinned by tests/fixtures/tuned/, and none of
engineering's escalation words may reach it (test_profile_tuned_text.py). This file shows each word is read where the
text used to be, shown with a marker no shipped profile contains.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from autornd.config import settings
from autornd.engine.phases import escalation_system_prompt
from autornd.knowledge.context import reset_rerank_mode
from autornd.models.verdicts import EscalationVerdict
from autornd.profiles import _general, framing, list_profiles, load_profile, set_profile
from autornd.specialists.registry import reload_specialists
from tests.prompt_capture import capture_all

ROOT = Path(__file__).resolve().parent.parent
MAIN = json.loads((ROOT / "tests" / "fixtures" / "words" / "escalation_main.json").read_text(encoding="utf-8"))
ENGINEERING_FAMILY = ("engineering", "example", "cupline", "tier4")

WORDS = ("escalation_persona", "escalation_worker", "escalation_flaw", "escalation_correction",
         "escalation_scope", "escalation_plan_heading")
MARKS = {key: f"<<{key}>>" for key in WORDS}


def _use(name: str) -> None:
    set_profile(load_profile(name))
    reload_specialists()


def _use_marked(**marks: str) -> None:
    """Engineering's team and words, with these words replaced."""
    base = load_profile("engineering")
    set_profile(replace(base, framing={**base.framing, **marks}))
    reload_specialists()


async def _escalation(monkeypatch) -> str:
    monkeypatch.setattr(settings, "model_research", "test-provider/test-research")
    monkeypatch.setattr(settings, "model_ranker", "test-provider/test-rank")
    reset_rerank_mode()
    return (await capture_all())["escalation"]["system"]


class TestTheSixWordsEveryProfileResolves:
    def test_general_declares_them(self):
        assert set(WORDS) <= set(_general().framing)

    def test_every_profile_resolves_each_to_a_text_that_is_not_blank(self):
        for name in list_profiles():
            _use(name)
            words = framing()
            for key in WORDS:
                assert isinstance(words[key], str) and words[key].strip(), (name, key)

    def test_the_engineering_family_has_the_words_the_prompt_was_written_with(self):
        for name in ENGINEERING_FAMILY:
            _use(name)
            assert escalation_system_prompt(2) == MAIN["system_n2"], name
            assert framing()["escalation_plan_heading"] == MAIN["plan_heading"], name

    def test_no_other_profile_is_sent_engineerings_names(self):
        for name in list_profiles():
            if name in ENGINEERING_FAMILY:
                continue
            _use(name)
            text = escalation_system_prompt(2) + framing()["escalation_plan_heading"]
            for old in ("Principal Systems Architect", "Implementation", "architectural flaw", "Architect's Plan",
                        "missing dependencies", "current architecture"):
                assert old not in text, (name, old)


class TestEveryWordIsReadWhereTheTextWasWritten:
    async def test_each_word_is_filled_at_its_own_place(self, monkeypatch):
        _use_marked(**MARKS)
        system = await _escalation(monkeypatch)
        assert "You are <<escalation_persona>>.\nThe <<escalation_worker>> agent has failed" in system
        assert '"root_cause_analysis": "The fundamental <<escalation_flaw>> causing the consecutive failures.' in system
        assert '"architectural_correction": "Corrected <<escalation_correction>> if the original plan was flawed.' in system
        assert "instructions for the <<escalation_worker>> model to succeed on its next attempt." in system
        assert "entirely outside the scope of <<escalation_scope>>.\n\n<<escalation_plan_heading>>\nCap the timer" in system
        for key in WORDS:
            assert system.count(MARKS[key]) == (2 if key == "escalation_worker" else 1), key

    async def test_no_engineering_name_is_left_when_every_word_is_replaced(self, monkeypatch):
        _use_marked(**MARKS)
        system = await _escalation(monkeypatch)
        for old in ("Principal Systems Architect", "Implementation agent", "Implementation model",
                    "architectural flaw", "Architect's Plan", "missing dependencies", "current architecture"):
            assert old not in system, old

    def test_a_word_is_text_and_is_not_read_again_as_a_template(self):
        _use_marked(escalation_persona="the {n} reviewer {escalation_scope}")
        assert "You are the {n} reviewer {escalation_scope}.\n" in escalation_system_prompt(4)

    def test_every_word_is_filled_under_every_profile_and_the_count_is_the_failures(self):
        for name in list_profiles():
            _use(name)
            text = escalation_system_prompt(3)
            assert "{escalation_" not in text and "{n}" not in text, name
            assert " has failed 3 consecutive validation attempts." in text, name
            assert '"rulings": [{"dissent": <number>, "upheld": true, "reason": "<one line>"}]' in text, name

    def test_the_words_follow_a_profile_switched_at_run_time(self):
        _use_marked(escalation_persona="a marker persona")
        assert "You are a marker persona." in escalation_system_prompt(1)
        _use("engineering")
        assert "You are the Principal Systems Architect for AutoRnD." in escalation_system_prompt(1)
        _use("legal")
        assert "You are the Supervising Attorney for AutoRnD." in escalation_system_prompt(1)


class TestTheRulesAreTheSameUnderEveryProfile:
    def test_the_rules_are_the_same_text_with_only_the_six_words_apart(self):
        """Blank the six words under every profile and the prompts are one text."""
        blanked = set()
        for name in list_profiles():
            _use(name)
            text = escalation_system_prompt(2)
            for key in WORDS[:5]:
                text = text.replace(framing()[key], "~")
            blanked.add(text)
        assert len(blanked) == 1

    def test_the_verdict_schema_text_names_no_engineering_role(self):
        """No model reads it, but it is the verdict's documentation (the prompt carries the same text, filled)."""
        for name in ("root_cause_analysis", "architectural_correction", "resolution_directive"):
            description = EscalationVerdict.model_fields[name].description
            assert "architectural flaw" not in description and "Implementation" not in description, name
