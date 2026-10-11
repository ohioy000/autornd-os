"""Ruling D43 (retired by D51): the request sets the scope
(ARCH-20261001-105).

Provider-free, through the real prompt builders: run_plan and
run_implement are called with the billing double, and the prompt
each sends is read off the call. D36's four rules are pinned by a
hash taken before D43 (D36 is owner-supplied and not a word of it
may move); Ruling D51 (R-b) moved the hash's end marker to the
first sentence of the block that replaced D43's scope rule, which
is the same byte position, so the covered bytes are unchanged. The
implement prompt carries the scope sentence.
"""

from __future__ import annotations

import hashlib

from autornd.engine import phases
from autornd.models.verdicts import PlanVerdict, TriageVerdict
from autornd.specialists.registry import get_specialists
from tests.conftest import make_mock_client

# sha256 of D36's block, from "Rules for the plan (each measured
# 2026-09-30, ..." up to the first sentence of the block that follows
# it, taken from main 81da1e0 before D43. Ruling D51 (R-b) moved the
# end marker from D43's sentence "The success criteria are the most
# important thing you produce." to the first sentence of the block that
# replaced it ("You do not write the test this work is judged by."):
# the deletion point is the insertion point, so the bytes the hash
# covers are unchanged.
D36_SHA256 = "5bd19bc0cfb39888b969bd65d10134fb0638446ecb8140b2aa114929dceb0928"
D36_START = "Rules for the plan (each measured 2026-09-30, each a loop-killer when broken):"
D36_END = "You do not write the test this work is judged by."
IMPLEMENT_SENTENCE = ("Answer the request, and include the plan's falsifiers, kill "
                      "triggers or assumption tables only if the request asks for them.")

TRIAGE = TriageVerdict(domains=["electrical"], risk="low",
                       specialists=["hardware_engineer"], summary="Logic")
PLAN = PlanVerdict(ready=True, plan="OR the doors, AND with the brake.", blockers=[],
                   success_criteria=["The answer names an OR and an AND gate"])
RESPONSES = {"default": {"ready": True, "plan": "p", "blockers": [],
                         "success_criteria": ["c"], "done": True, "green": True,
                         "red_cause": None, "summary": "s"}}


async def _plan_prompt() -> str:
    client = make_mock_client(RESPONSES)
    await phases.run_plan(client, "Describe a logic circuit.", TRIAGE,
                          get_specialists(["hardware_engineer"]), context="")
    return client.chat_json.await_args.kwargs.get("user_message") or \
        client.chat_json.await_args.args[2]


async def _implement_prompt() -> str:
    client = make_mock_client(RESPONSES)
    await phases.run_implement(client, "Describe a logic circuit.", PLAN,
                               get_specialists(["hardware_engineer"]), iteration=1,
                               context="")
    return client.chat_json.await_args.kwargs.get("user_message") or \
        client.chat_json.await_args.args[2]


class TestThePlanPromptCarriesTheAsks:
    async def test_the_scope_rule_is_retired(self):
        # Convention 17: D51 (R-b) retired D43's scope rule — the plan
        # no longer writes success criteria, so there is nothing for the
        # rule to govern. The test that asserted the rule's presence is
        # the bug written down; it now asserts the retirement.
        prompt = await _plan_prompt()
        assert "Scope (Ruling D43)" not in prompt
        assert "success criteria" not in prompt.lower()
        assert "You do not write the test this work is judged by." in prompt
        assert "The asks, quoted from the request:" in prompt

    async def test_d36_is_byte_identical(self):
        prompt = await _plan_prompt()
        block = prompt[prompt.index(D36_START):prompt.index(D36_END)]
        assert hashlib.sha256(block.encode()).hexdigest() == D36_SHA256


class TestTheImplementPromptCarriesTheScopeSentence:
    async def test_the_sentence_is_present(self):
        assert IMPLEMENT_SENTENCE in await _implement_prompt()
