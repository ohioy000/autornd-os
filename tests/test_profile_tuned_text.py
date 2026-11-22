"""A profile that is not engineering teaches with its own examples, and none of engineering's.

The triage risk guide, the hazard sentence and the decision switches' questions are written in the profile's words
(tests/test_profile_prompt_words.py shows each word is read where the text used to be). This file guards what those
words say. Engineering keeps the physical-engineering examples the guide was calibrated on; every other profile
teaches with the examples of its own field, and the universal profile with examples from several. Three things hold
for every profile that is not engineering:

 - what its models are sent is the text that was read and ruled on: a compact fixture per profile holds the rendered
   risk guide, the hazard lines and the switch questions, and a change to a word is a change to a fixture;
 - none of engineering's examples reaches a model (the lexicon below is taken from engineering's own ten words, and
   is shown to be found under engineering, so a scan that cannot match cannot pass);
 - the rules around the examples are untouched. The guide's rules live in the code and are the same for every
   profile, because the risk axis must not move with the profile; a passage carries the rule it is spliced into, and
   each passage must still say it, and a hazard text must keep both injury to a person and damage to equipment.

WRITE_GOLDEN=1 writes the fixtures; a change to one is read before it is kept.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from autornd.config import settings
from autornd.knowledge.context import request_demands_sources, reset_rerank_mode
from autornd.profiles import framing, load_profile, set_profile
from autornd.specialists.registry import reload_specialists
from tests.prompt_capture import NEUTRAL_SEATS, capture_all, switch_requests

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "tuned"
WRITE_GOLDEN = os.environ.get("WRITE_GOLDEN") == "1"

TUNED = ("general", "studio")
HAZARD_SITES = ("domain_review", "validate", "review_collaborative", "review_adversarial", "doublecheck")

# Engineering's own examples, one distinctive token each, taken from its ten words. A profile that teaches with its
# own field's examples carries none of them.
LEXICON = ("lintel", "structural loading", "pressure vessel", "load path", "control surface", "wiring, installing",
           "actuating", "sensor", "aeration", "live stock", "tank of", "tolerance", "sizing", "datasheet",
           "chain of conversions", "design figure", "damage equipment", "selecting a component", "a part is cut",
           "on a machine")


def _use(name: str) -> None:
    set_profile(load_profile(name))
    reload_specialists()


async def _view(name: str, monkeypatch) -> dict:
    """What a profile's models are taught with: the risk guide, the hazard lines, the switch questions."""
    monkeypatch.setattr(settings, "model_research", "test-provider/test-research")
    monkeypatch.setattr(settings, "model_ranker", "test-provider/test-rank")
    reset_rerank_mode()
    _use(name)
    captured = await capture_all(NEUTRAL_SEATS if name != "engineering" else None)
    triage = captured["triage"]["user"]
    return {
        "guide": triage[triage.index("Risk guide"):triage.index("Do not escalate")],
        "hazard": [line for site in HAZARD_SITES for line in captured[site]["user"].splitlines()
                   if "followed as written" in line],
        "switches": await switch_requests(),
    }


async def test_write_tuned_fixtures(monkeypatch) -> None:
    """WRITE_GOLDEN=1 writes one fixture per tuned profile."""
    if not WRITE_GOLDEN:
        pytest.skip("WRITE_GOLDEN is not set")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name in TUNED:
        text = json.dumps(await _view(name, monkeypatch), indent=1, ensure_ascii=False, sort_keys=True)
        (FIXTURE_DIR / f"{name}.json").write_text(text, encoding="utf-8")


class TestTheTextIsTheTextThatWasRead:
    async def test_each_tuned_profile_renders_its_fixture(self, monkeypatch):
        for name in TUNED:
            want = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
            got = await _view(name, monkeypatch)
            changed = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))
            assert not changed, f"{name}: these changed: {changed}"

    def test_every_tuned_profile_has_a_fixture_and_every_fixture_a_profile(self):
        assert {p.stem for p in FIXTURE_DIR.glob("*.json")} == set(TUNED)


class TestNoEngineeringExampleIsTaughtOutsideEngineering:
    async def test_the_lexicon_is_what_engineering_teaches_with(self, monkeypatch):
        """Every entry is found under engineering, so the scan below can fail."""
        text = json.dumps(await _view("engineering", monkeypatch), ensure_ascii=False).lower()
        missing = [word for word in LEXICON if word not in text]
        assert not missing, f"entries engineering does not use: {missing}"

    async def test_no_tuned_profile_carries_one(self, monkeypatch):
        for name in TUNED:
            text = json.dumps(await _view(name, monkeypatch), ensure_ascii=False).lower()
            found = [word for word in LEXICON if word in text]
            assert not found, f"{name} teaches with engineering's {found}"


class TestTheRulesStayTheSame:
    """Every passage is spliced into a rule the code states; a profile's own passage must still say its part."""

    ANCHORS = {
        "risk_paper_examples": ("critical while still",),
        "risk_high_examples": ("the answer ", "safety-critical in function even while still",
                               "or it ships as core system behaviour, a security boundary, or data integrity."),
        "risk_medium_examples": ("the answer is still a decision, reversible until",),
        "risk_protective_example": ("at least high rather than medium",
                                    "It is critical only if a person can be harmed",
                                    "however much of it, is high"),
    }

    def test_each_passage_still_says_the_rule_it_carries(self):
        for name in ("engineering",) + TUNED:
            _use(name)
            words = framing()
            for key, anchors in self.ANCHORS.items():
                text = " ".join(words[key].split())
                for anchor in anchors:
                    assert anchor in text, f"{name}.{key} lost: {anchor!r}"

    def test_a_hazard_text_keeps_injury_to_a_person_and_damage_to_equipment(self):
        for name in ("engineering",) + TUNED:
            _use(name)
            text = framing()["hazard_harm"]
            assert "injure" in text and "person" in text and "damage" in text and "equipment" in text, name


class TestTheCitationPhrasesOutsideEngineering:
    def test_a_tuned_profile_has_no_datasheet_phrase_and_keeps_the_generic_ones(self):
        for name in TUNED:
            _use(name)
            assert not request_demands_sources("What is the limit per the datasheet?"), name
            assert not request_demands_sources("Read the figure from the datasheet."), name
            assert request_demands_sources("Answer with sources."), name
            assert request_demands_sources("According to the statute, what is the notice period?"), name
