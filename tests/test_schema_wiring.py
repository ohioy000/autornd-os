"""Every phase that declares a schema must pass it into the retry loop.

**The pattern in force.** `chat_json` validates a reply against a schema and, on
failure, retries up to three times with a note saying exactly what was rejected.
A phase that constructs its verdict *after* the call instead gets none of that:
one malformed reply and the run raises.

This class has now bitten three times:

- §6.8: `except ValidationError` sat *below* `except ValueError`, which it
  subclasses, so every schema violation was logged as a parse failure and the
  retry never carried a useful correction.
- §6.8: the rerank fallback latched on any exception, making a doomed call every
  workflow thereafter.
- 006 §13: `implement` never passed its schema at all. Two of four live traces
  died on it — one verdict missing `green`, another missing `done` — and were
  read as convergence failures, which is how B7's premise came to be built on
  evidence that had never reached the loop. A source read then found
  `escalation` had the identical defect, in the worst possible place: the
  longest input in the system, read only after the loop has burned every
  iteration it had.

**The whole suite was green through all of it**, because test doubles return
well-formed verdicts. Nothing short of pinning the call sites catches this, so
the call sites are pinned.

**The rule for new work: a phase whose workflow node declares a schema passes
that schema into its client call, and adds itself here.**
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from autornd.models.verdicts import (
    DoubleCheckVerdict,
    EscalationVerdict,
    ImplementVerdict,
    PlanVerdict,
    ReviewVerdict,
    TriageVerdict,
    ValidateVerdict,
)
from autornd.routing.openrouter import ModelResponse, OpenRouterClient


def capturing_client(reply: dict):
    """Records the `schema=` of every chat_json call made through it."""
    client = OpenRouterClient(api_key="test")
    seen: list[object] = []

    async def chat_json(function, system_prompt, user_message, schema=None, **kw):
        seen.append(schema)
        client._account(function, 0.001)
        return dict(reply), ModelResponse(content=json.dumps(reply), model="mock",
                                          prompt_tokens=1, completion_tokens=1,
                                          cost=0.001)

    client.chat_json = AsyncMock(side_effect=chat_json)
    client.chat = AsyncMock()
    client.close = AsyncMock()
    client.captured_schemas = seen
    return client


@pytest.mark.asyncio
class TestEverySchemaBearingPhasePassesIt:
    async def test_triage(self):
        from autornd.engine import phases

        c = capturing_client({"domains": ["backend"], "risk": "medium",
                              "specialists": ["backend_engineer"], "summary": "s"})
        await phases.run_triage(c, "add retry")
        assert TriageVerdict in c.captured_schemas

    async def test_plan(self):
        from autornd.engine import phases
        from autornd.specialists.registry import get_specialist

        c = capturing_client({"ready": True, "plan": "Cap backoff at 60s.",
                              "blockers": [], "cost_estimate": None,
                              "success_criteria": ["Backoff capped at 60s"]})
        triage = TriageVerdict(domains=["backend"], risk="medium",
                               specialists=["backend_engineer"], summary="s")
        await phases.run_plan(c, "add retry", triage,
                              [get_specialist("backend_engineer")])
        assert PlanVerdict in c.captured_schemas

    async def test_implement(self):
        """006's traces died here."""
        from autornd.engine import phases
        from autornd.specialists.registry import get_specialist

        c = capturing_client({"done": True, "green": True, "red_cause": None,
                              "summary": "Backoff capped at 60s."})
        plan = PlanVerdict(ready=True, plan="p", success_criteria=["Backoff capped"])
        await phases.run_implement(
            c, "add retry", plan, [get_specialist("backend_engineer")], iteration=1)
        assert ImplementVerdict in c.captured_schemas, (
            "implement must validate inside the retry loop, not after it")

    async def test_validate(self):
        from autornd.engine import phases

        c = capturing_client({"green": True, "red_cause": None, "evidence": []})
        plan = PlanVerdict(ready=True, plan="p", success_criteria=["Backoff capped"])
        impl = ImplementVerdict(done=True, green=True, summary="s", iteration=1)
        await phases.run_validate(c, "add retry", plan, impl)
        assert ValidateVerdict in c.captured_schemas

    async def test_escalation(self):
        """The longest input in the system, read at the most expensive moment."""
        from autornd.engine import phases

        c = capturing_client({"root_cause_analysis": "a",
                              "architectural_correction": None,
                              "resolution_directive": "do x",
                              "requires_human": False})
        plan = PlanVerdict(ready=True, plan="p", success_criteria=["c"])
        triage = TriageVerdict(domains=["backend"], risk="high",
                               specialists=["backend_engineer"], summary="s")
        await phases.run_escalation_autopsy(
            c, "add retry", plan, triage,
            [{"iteration": 1, "red_cause": "x", "implement_summary": "s",
              "evidence": []}], "")
        assert EscalationVerdict in c.captured_schemas, (
            "escalation must validate inside the retry loop, not after it")

    async def test_doublecheck(self):
        from autornd.engine import phases

        c = capturing_client({"ship": True, "confidence": "high",
                              "critical_issues": [], "recommendations": [],
                              "verdict": "ok"})
        plan = PlanVerdict(ready=True, plan="p", success_criteria=["c"])
        impl = ImplementVerdict(done=True, green=True, summary="s", iteration=1)
        await phases.run_doublecheck(c, "add retry", plan, impl)
        assert DoubleCheckVerdict in c.captured_schemas


@pytest.mark.asyncio
class TestTheDocumentedExceptions:
    """Two phases deliberately do not pass a schema, and should not start.

    Both are free-form mutators: they return prose that another verdict absorbs
    rather than a verdict of their own, so there is no schema to validate
    against and a retry would have nothing to correct toward.
    """

    async def test_feasibility_is_free_form_by_design(self):
        from autornd.engine import phases
        from autornd.specialists.registry import get_specialist

        c = capturing_client({"feasible": True, "concerns": [], "blockers": []})
        plan = PlanVerdict(ready=True, plan="p", success_criteria=["c"])
        triage = TriageVerdict(domains=["backend"], risk="medium",
                               specialists=["backend_engineer"], summary="s")
        await phases.run_plan_feasibility(
            c, "add retry", triage, plan, [get_specialist("backend_engineer")], "")
        assert c.captured_schemas == [None], (
            "feasibility folds into PlanVerdict; it has no verdict of its own")

    async def test_domain_review_is_free_form_by_design(self):
        from autornd.engine import phases
        from autornd.specialists.registry import get_specialist

        c = capturing_client({"concerns": [], "critical": False})
        await phases.run_domain_review(
            c, "add retry", PlanVerdict(ready=True, plan="p",
                                        success_criteria=["c"]),
            "summary", [get_specialist("backend_engineer")], "")
        assert c.captured_schemas == [None], (
            "domain review mutates the implement verdict; it has none of its own")


@pytest.mark.asyncio
class TestReviewAggregationAcceptsEveryShapeTheSchemaDoes:
    """`ReviewFinding` was made lenient because a reviewer using `issue` instead
    of `detail` lost three entire reviews at the final phase, with the findings
    in hand. That leniency was then unreachable: the aggregation called
    `f.get("severity")` on the raw item, so a bare string — precisely the shape
    the leniency exists for — raised AttributeError *after* every reviewer had
    been paid. Widening a schema is worthless if the code upstream of it still
    assumes one shape.
    """

    @staticmethod
    async def _review_with(findings):
        from autornd.engine import phases
        from autornd.specialists.registry import get_specialist

        c = capturing_client({"ship": False, "findings": findings,
                              "verdict": "Blocked."})
        plan = PlanVerdict(ready=True, plan="p", success_criteria=["c"])
        impl = ImplementVerdict(done=True, green=True, summary="s", iteration=1)
        triage = TriageVerdict(domains=["backend"], risk="medium",
                               specialists=["backend_engineer"], summary="s")
        return await phases.run_review(
            c, "add retry", triage, plan, impl,
            [get_specialist("backend_engineer")], "")

    async def test_findings_as_bare_strings(self):
        verdict, _ = await self._review_with(["The backoff is uncapped"])
        assert verdict.findings
        assert "uncapped" in verdict.findings[0].detail

    async def test_findings_with_an_aliased_detail_key(self):
        verdict, _ = await self._review_with(
            [{"issue": "The backoff is uncapped", "severity": "critical"}])
        assert "uncapped" in verdict.findings[0].detail
        assert not verdict.ship, "a critical finding still blocks"

    async def test_findings_missing_severity(self):
        verdict, _ = await self._review_with([{"detail": "No jitter applied"}])
        assert verdict.findings[0].severity == "medium", "the schema default"

    async def test_a_mixture_of_shapes_in_one_review(self):
        verdict, _ = await self._review_with([
            "a bare string",
            {"issue": "aliased", "severity": "high"},
            {"detail": "no severity"},
        ])
        assert len(verdict.findings) == 3
        assert not verdict.ship, "the high finding blocks"


class TestErrorsCarryTheProvidersMessage:
    """A status code is not a diagnosis.

    A live 403 was read as rate limiting and blamed on running two sweeps
    concurrently. The response body said `Workspace weekly budget of $10.00
    exceeded` — a different problem with a different fix, discarded by
    `raise_for_status` at the moment of raising. The provider puts the reason in
    the body for every error class it returns; it travels with the exception now.
    """

    @staticmethod
    def _response(status: int, payload):
        import httpx

        return httpx.Response(
            status_code=status, json=payload,
            request=httpx.Request("POST", "https://example.org/api/v1/chat/completions"),
        )

    def test_the_message_survives_the_raise(self):
        import httpx
        import pytest as _pytest

        from autornd.routing.openrouter import _raise_for_status

        resp = self._response(403, {"error": {
            "message": "Workspace weekly budget of $10.00 exceeded.", "code": 403}})
        with _pytest.raises(httpx.HTTPStatusError) as exc:
            _raise_for_status(resp, "chat/completions")
        assert "weekly budget" in str(exc.value)
        assert "403" in str(exc.value)

    def test_a_body_that_is_not_json_still_reaches_the_caller(self):
        import httpx
        import pytest as _pytest

        from autornd.routing.openrouter import _raise_for_status

        resp = httpx.Response(
            status_code=502, text="upstream exploded",
            request=httpx.Request("POST", "https://example.org/x"))
        with _pytest.raises(httpx.HTTPStatusError) as exc:
            _raise_for_status(resp, "chat/completions")
        assert "upstream exploded" in str(exc.value)

    def test_success_passes_through_untouched(self):
        from autornd.routing.openrouter import _raise_for_status

        _raise_for_status(self._response(200, {"ok": True}), "chat/completions")
