"""`green` is derived from `red_cause`, loudly.

**Why.** Every prompt that asks for `green` defines it in the same breath —
"green: true if it satisfies the criteria; red_cause: null if green, otherwise
what is wrong". The two are one fact stated twice, and the model reliably
supplies the cause and omits the flag.

Measured twice, four blueprints apart. In 006 two of four convergence traces
died on `ImplementVerdict` rejecting a reply that carried `done` and `red_cause`
and no `green`; the schema was wired into the retry loop so the model would be
told what was wrong and asked again. In 010 two of four died the same way **after
all three retries were spent** — each attempt carrying the rejection text, each
coming back without the field. The wiring worked; the model did not comply.

**The rule (convention 20): tolerate omission of a derivable field, refuse loss
of a non-derivable one.** `done` stays required because nothing else in the
verdict implies it. And every resolution is counted, because a fix that hides
its own trigger stops anyone noticing when it is no longer needed.
"""

from __future__ import annotations

import pytest

from autornd.models.verdicts import (
    ImplementVerdict,
    ValidateVerdict,
    normalisations,
    reset_normalisations,
)


def implement(**kw):
    return ImplementVerdict(**{"done": True, "summary": "s", **kw})


class TestTheTruthTable:
    """All six rows, on both verdicts that carry the contract."""

    @pytest.mark.parametrize("model", [ImplementVerdict, ValidateVerdict])
    def test_absent_green_with_a_cause_is_red(self, model):
        extra = {"done": True, "summary": "s"} if model is ImplementVerdict else {}
        assert model(red_cause="criterion 4 fails", **extra).green is False

    @pytest.mark.parametrize("model", [ImplementVerdict, ValidateVerdict])
    def test_absent_green_with_no_cause_is_green(self, model):
        extra = {"done": True, "summary": "s"} if model is ImplementVerdict else {}
        assert model(**extra).green is True

    def test_green_false_with_a_cause_passes_through(self):
        v = implement(green=False, red_cause="criterion 4 fails")
        assert v.green is False and v.red_cause == "criterion 4 fails"

    def test_green_true_with_no_cause_passes_through(self):
        assert implement(green=True).green is True

    def test_green_true_with_a_cause_is_coerced_red(self):
        """The conservative side: a false red costs an iteration, a false green
        ships work nobody checked."""
        assert implement(green=True, red_cause="criterion 4 fails").green is False

    def test_green_false_with_no_cause_is_refused(self):
        """The one case that loses information — something is wrong and the
        verdict will not say what. The retry machinery exists to ask."""
        with pytest.raises(ValueError, match="must name its cause"):
            implement(green=False)

    def test_a_whitespace_cause_is_not_a_cause(self):
        assert implement(red_cause="   ").green is True


class TestWhatStaysRequired:
    def test_done_is_still_required(self):
        """Informationally independent: nothing in the verdict implies whether
        the work is finished, so its omission is a real loss and the retry loop
        is the right place to handle it."""
        with pytest.raises(Exception):
            ImplementVerdict(summary="s", red_cause="x")


class TestTheResolutionIsCounted:
    def test_each_normalisation_increments_the_counter(self):
        reset_normalisations()
        implement(red_cause="a")          # derived red
        implement()                        # derived green
        implement(green=True, red_cause="b")   # coerced
        assert normalisations() == 3

    def test_a_well_formed_verdict_counts_nothing(self):
        reset_normalisations()
        implement(green=False, red_cause="a")
        implement(green=True)
        assert normalisations() == 0

    def test_the_counter_resets(self):
        implement(red_cause="a")
        reset_normalisations()
        assert normalisations() == 0


class TestProgrammaticMutationIsUnaffected:
    """The domain-review mutation flips `green` after construction. A
    construction-time validator must not re-fire on assignment and must not
    demand a cause it is about to be given."""

    def test_flipping_green_false_post_construction_does_not_raise(self):
        v = implement(green=True)
        v.green = False
        assert v.green is False, "no validator should re-run on assignment"

    def test_the_domain_review_mutation_shape_still_works(self):
        from autornd.engine.phases import render_domain_concerns

        v = implement(green=True)
        v.domain_concerns = ["Heatsink undersized"]
        v.green = False
        v.red_cause = render_domain_concerns(v.domain_concerns)
        assert v.green is False
        assert "Heatsink undersized" in v.red_cause


class TestTheRawDictPathAgrees:
    """`run_implement` reads `green` off the reply dict before the verdict is
    constructed, to decide whether to run domain review. An omitted green read
    as falsy there would skip the reviewers entirely — the opposite of what an
    unqualified reply means."""

    @pytest.mark.asyncio
    async def test_an_omitted_green_still_runs_domain_review(self):
        import json
        from unittest.mock import AsyncMock

        from autornd.models.verdicts import PlanVerdict
        from autornd.routing.openrouter import ModelResponse, OpenRouterClient
        from autornd.specialists.registry import get_specialist

        seen: list[str] = []

        client = OpenRouterClient(api_key="test")

        async def chat_json(function, system_prompt, user_message, **kw):
            lowered = user_message.lower()
            if "from your domain perspective" in lowered:
                seen.append("domain_review")
                data = {"concerns": [], "critical": False}
            else:
                # done and a summary, no green, no cause — the shape that died.
                data = {"done": True, "summary": "Capped backoff at 60s."}
            client._account(function, 0.001)
            return data, ModelResponse(content=json.dumps(data), model="m",
                                       prompt_tokens=1, completion_tokens=1,
                                       cost=0.001)

        client.chat_json = AsyncMock(side_effect=chat_json)
        client.close = AsyncMock()

        from autornd.engine import phases

        verdict, _ = await phases.run_implement(
            client, "Add retry",
            PlanVerdict(ready=True, plan="p", success_criteria=["Backoff capped"]),
            [get_specialist("backend_engineer"), get_specialist("frontend_engineer")],
            iteration=1,
            # Reviewers are only selected when a primary domain names a lead —
            # without it select_lead returns none and domain review is skipped
            # for a reason that has nothing to do with green.
            primary_domain="backend")

        assert verdict.green is True, "an unqualified reply is not a red one"
        assert seen == ["domain_review"], (
            "domain review must still run — reading the raw dict must agree "
            "with what the verdict resolves to")
