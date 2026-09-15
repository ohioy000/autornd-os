"""The malformed-verdict rate must be readable from the record, not from stderr.

**Why this exists.** `chat_json` has always logged a schema rejection at
WARNING. The eval CLI configures no logging, so those lines reached only
Python's lastResort stderr handler and lived as long as the shell redirect that
caught them. When 011 came to compute the rate across "all retained history",
three run logs of nine survived — and the two runs whose rejections the whole
question turned on were not among them.

So the pair is counted on the client and lands in the JSONL unit record:

- `normalised_verdicts` — replies the truth table repaired.
- `rejections_by_tier` — replies it could not, retries included.

They must be read together. The green resolution converts the second into the
first, and a measurement that sees only one of them cannot tell a fixed
population from a shrinking one.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from autornd.routing.openrouter import ModelResponse, OpenRouterClient


class Shape(BaseModel):
    done: bool


def replying_client(*contents, providers=()) -> OpenRouterClient:
    """A client whose chat returns the given bodies, optionally per provider."""
    client = OpenRouterClient(api_key="test")
    bodies = list(contents)
    servings = list(providers) or [None] * len(bodies)

    async def chat(function, system_prompt, user_message, **kw):
        body, provider = bodies.pop(0), servings.pop(0)
        client._account(function, 0.001, provider=provider,
                        prompt_tokens=10, completion_tokens=2)
        return ModelResponse(content=body, model="mock", provider=provider,
                             prompt_tokens=10, completion_tokens=2, cost=0.001)

    client.chat = chat  # type: ignore[method-assign]
    return client


@pytest.mark.asyncio
async def test_rejection_is_counted_per_tier():
    client = replying_client('{"wrong": 1}', '{"done": true}')
    parsed, _ = await client.chat_json(
        function="implement", system_prompt="s", user_message="u",
        schema=Shape, max_retries=3)
    assert parsed == {"done": True}
    # One rejection, one accepted reply — two billed calls, one rejection.
    assert client.rejections_by_function == {"implement": 1}
    assert client.calls_by_function == {"implement": 2}


@pytest.mark.asyncio
async def test_the_refusing_serving_is_named():
    """"The engineering tier refused" names no one; a dozen providers serve it."""
    client = replying_client('{"x": 1}', '{"y": 2}', '{"done": true}',
                             providers=("Wafer", "Wafer", "Alibaba"))
    await client.chat_json(function="implement", system_prompt="s",
                           user_message="u", schema=Shape, max_retries=3)
    assert client.rejections_by_function == {"implement": 2}
    assert client.rejections_by_provider == {"Wafer": 2}


@pytest.mark.asyncio
async def test_exhausted_retries_count_every_rejection():
    client = replying_client('{"a": 1}', '{"b": 2}', '{"c": 3}')
    with pytest.raises(Exception):
        await client.chat_json(
            function="implement", system_prompt="s", user_message="u",
            schema=Shape, max_retries=3)
    # The death that killed four traces across 006 and 010 is three rejections,
    # not one. Counting only the last would understate the rate threefold.
    assert client.rejections_by_function == {"implement": 3}


@pytest.mark.asyncio
async def test_a_parse_failure_is_not_a_rejection():
    """Unparseable text and wrong-shaped JSON are different defects."""
    client = replying_client("not json at all", '{"done": true}')
    await client.chat_json(function="implement", system_prompt="s",
                           user_message="u", schema=Shape, max_retries=3)
    assert client.rejections_by_function == {}


@pytest.mark.asyncio
async def test_no_schema_means_no_rejections():
    client = replying_client('{"anything": 1}')
    await client.chat_json(function="triage", system_prompt="s",
                           user_message="u", max_retries=3)
    assert client.rejections_by_function == {}


def test_reset_clears_the_counter():
    client = OpenRouterClient(api_key="test")
    client.rejections_by_function["implement"] = 4
    client.rejections_by_provider["Wafer"] = 4
    client.reset_accounting()
    assert client.rejections_by_function == {}
    assert client.rejections_by_provider == {}


def test_the_counter_reaches_the_unit_record(tmp_path):
    """A counter the JSONL does not carry is the stderr problem again."""
    from autornd.evals.runner import ResultsLog, ScenarioRun
    from autornd.evals.scenario import Scenario

    run = ScenarioRun(
        scenario=Scenario(id="conv_probe", request="o"),
        results=[], calls=2, seconds=1.0,
        normalised_verdicts=3,
        rejections_by_tier={"implement": 2, "validate": 1},
        rejections_by_provider={"Wafer": 3},
    )
    log = ResultsLog(tmp_path / "units.jsonl")
    log.record(run, workflow="engineering-rnd", repetition=1)

    unit = [json.loads(line) for line in (tmp_path / "units.jsonl").read_text()
            .splitlines()][-1]
    assert unit["record"] == "unit"
    assert unit["rejections_by_tier"] == {"implement": 2, "validate": 1}
    assert unit["rejections_by_provider"] == {"Wafer": 3}
    # The pair travels together or the rate cannot be read.
    assert unit["normalised_verdicts"] == 3
