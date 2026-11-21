"""The reader tier (owner's ruling, 2026-11-20): small models read the long
pages a lookup fetched, many stretches at once, and copy back words.

What is pinned: with the tier unset nothing changes; with it set, a passage
counts only where the page holds it (the reader's say-so is never enough);
a reader that fails costs the lookup nothing; a spend refusal still stops the
run; and every call goes out under the reader function, never as an
engineering call by default.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from autornd import config
from autornd.knowledge import research
from autornd.knowledge.fetch import Source
from autornd.routing import openrouter
from autornd.routing.openrouter import BudgetExceeded, ModelResponse

URL = "https://example.org/standard.pdf"
ANSWER_LINE = "The maximum permitted EIRP for this class is 4 W in the band."
OTHER_LINE = "The minimum 6 dB bandwidth must be at least 500 kHz in the band."


def long_page() -> str:
    """About 16,000 characters, one line to a sentence, two of them the point."""
    lines = [f"Clause {n} sets out an unrelated administrative requirement for "
             f"item {n} of the schedule and nothing else." for n in range(140)]
    lines[30] = ANSWER_LINE
    lines[100] = OTHER_LINE
    return "\n".join(lines)


def reader_reply(passages):
    return ModelResponse(content=json.dumps({"passages": passages}),
                         model="vendor/reader", prompt_tokens=10,
                         completion_tokens=10, cost=0.0001, citations=[])


@pytest.fixture
def served(monkeypatch):
    page = long_page()

    async def fetch(url):
        return Source(url=url, status="fetched", text=page,
                      fetched_at="2026-11-20T00:00:00Z", sha256="cd" * 32)

    monkeypatch.setattr(research, "fetch_source", fetch)
    return page


def tier(monkeypatch, model="vendor/reader"):
    monkeypatch.setattr(config.settings, "model_reader", model)


TERMS = {"eirp", "maximum", "permitted", "bandwidth"}


@pytest.mark.asyncio
class TestTheTierIsOff:
    async def test_unset_means_no_call_and_the_same_quotes(self, monkeypatch, served):
        tier(monkeypatch, "")
        client = AsyncMock()
        with_client, docs = await research._read_documents(
            {URL: "p"}, TERMS, client, "what is the EIRP?")
        without, _ = await research._read_documents({URL: "p"}, TERMS)
        client.chat.assert_not_called()
        assert [q.text for q in with_client] == [q.text for q in without]
        assert "reader" not in docs[0]

    async def test_a_page_short_enough_to_hand_on_whole_is_not_read(self, monkeypatch):
        tier(monkeypatch)

        async def fetch(url):
            return Source(url=url, status="fetched", text=ANSWER_LINE,
                          fetched_at="2026-11-20T00:00:00Z", sha256="cd" * 32)

        monkeypatch.setattr(research, "fetch_source", fetch)
        client = AsyncMock()
        await research._read_documents({URL: "p"}, TERMS, client, "q")
        client.chat.assert_not_called()


@pytest.mark.asyncio
class TestTheTierIsOn:
    async def test_a_copied_passage_the_page_holds_is_handed_on(self, monkeypatch, served):
        tier(monkeypatch)
        client = AsyncMock()
        client.chat = AsyncMock(return_value=reader_reply([ANSWER_LINE]))
        quotes, docs = await research._read_documents(
            {URL: "p"}, TERMS, client, "what is the EIRP?")
        assert client.chat.await_count >= 1
        assert all(c.kwargs["function"] == "reader" for c in client.chat.await_args_list)
        held = [q for q in quotes if q.text == ANSWER_LINE]
        assert held and held[0].status == "found"
        assert docs[0]["reader"]["passages"] == 1 and docs[0]["reader"]["dropped"] == 0

    async def test_the_reader_is_asked_not_to_reason(self, monkeypatch, served):
        """Measured live: with reasoning on, the model spent its whole budget
        thinking and returned nothing. Break-proof: remove the option and this
        fails."""
        tier(monkeypatch)
        client = AsyncMock()
        client.chat = AsyncMock(return_value=reader_reply([]))
        await research._read_documents({URL: "p"}, TERMS, client, "q")
        assert all(c.kwargs["reasoning"] == {"enabled": False}
                   for c in client.chat.await_args_list)

    async def test_a_passage_not_on_the_page_is_dropped(self, monkeypatch, served):
        """The reader's say-so is never enough. Break-proof: if the check
        quote_found is taken out of _read_with_readers, this fails."""
        tier(monkeypatch)
        invented = "The maximum permitted EIRP for this class is 40 W in the band."
        client = AsyncMock()
        client.chat = AsyncMock(return_value=reader_reply([invented, ANSWER_LINE]))
        quotes, docs = await research._read_documents(
            {URL: "p"}, TERMS, client, "what is the EIRP?")
        assert not any(invented in q.text for q in quotes)
        assert docs[0]["reader"]["dropped"] >= 1
        assert any(q.text == ANSWER_LINE for q in quotes)

    async def test_a_summary_is_not_a_passage(self, monkeypatch, served):
        tier(monkeypatch)
        client = AsyncMock()
        client.chat = AsyncMock(return_value=reader_reply(
            ["The page says the limit is four watts, and a bandwidth floor applies."]))
        quotes, docs = await research._read_documents(
            {URL: "p"}, TERMS, client, "q")
        assert docs[0]["reader"]["passages"] == 0
        assert all(q.status == "found" for q in quotes)

    async def test_the_stretches_are_read_at_once(self, monkeypatch, served):
        tier(monkeypatch)
        running = peak = 0

        async def chat(**kw):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.05)
            running -= 1
            return reader_reply([])

        client = AsyncMock()
        client.chat = AsyncMock(side_effect=chat)
        await research._read_documents({URL: "p"}, TERMS, client, "q")
        assert client.chat.await_count >= 2 and peak >= 2

    async def test_a_passage_already_among_the_chosen_stretches_is_not_repeated(
            self, monkeypatch, served):
        tier(monkeypatch)
        client = AsyncMock()
        client.chat = AsyncMock(return_value=reader_reply([ANSWER_LINE]))
        quotes, _ = await research._read_documents(
            {URL: "p"}, TERMS, client, "q")
        # the same words from every stretch's call, handed on once
        assert sum(ANSWER_LINE in q.text and q.text == ANSWER_LINE for q in quotes) <= 1

    async def test_a_failing_reader_costs_the_lookup_nothing(self, monkeypatch, served):
        tier(monkeypatch)
        client = AsyncMock()
        client.chat = AsyncMock(side_effect=RuntimeError("provider down"))
        quotes, docs = await research._read_documents(
            {URL: "p"}, TERMS, client, "q")
        without, _ = await research._read_documents({URL: "p"}, TERMS)
        assert [q.text for q in quotes] == [q.text for q in without]
        assert docs[0]["reader"]["passages"] == 0

    async def test_a_spend_refusal_still_stops_the_run(self, monkeypatch, served):
        tier(monkeypatch)
        client = AsyncMock()
        client.chat = AsyncMock(side_effect=BudgetExceeded("over"))
        with pytest.raises(BudgetExceeded):
            await research._read_documents({URL: "p"}, TERMS, client, "q")

    async def test_a_reply_that_is_not_the_typed_form_is_no_passages(
            self, monkeypatch, served):
        tier(monkeypatch)
        client = AsyncMock()
        client.chat = AsyncMock(return_value=ModelResponse(
            content="Sure! The answer is 4 W.", model="vendor/reader",
            prompt_tokens=1, completion_tokens=1, cost=0.0, citations=[]))
        quotes, docs = await research._read_documents(
            {URL: "p"}, TERMS, client, "q")
        assert docs[0]["reader"]["passages"] == 0


class TestTheExcerptChooser:
    def test_the_defaults_are_what_a_lookup_always_handed_on(self):
        out = research._excerpts(long_page(), TERMS)
        assert len(out) <= research.DOCUMENT_EXCERPTS
        assert all(len(x) <= research.DOCUMENT_EXCERPT_CHARS for x in out)

    def test_a_longer_stretch_and_a_higher_count_are_honoured(self):
        out = research._excerpts(long_page(), TERMS,
                                 research.READER_CHUNK_CHARS, research.READER_CHUNKS)
        assert max(len(x) for x in out) > research.DOCUMENT_EXCERPT_CHARS
        assert all(len(x) <= research.READER_CHUNK_CHARS for x in out)


class TestTheTierIsWired:
    def test_it_ships_empty_and_the_example_names_it(self):
        assert config.Settings.model_fields["model_reader"].default == ""
        text = (Path(__file__).resolve().parent.parent / ".env.example").read_text()
        assert "MODEL_READER=\n" in text

    def test_the_function_is_routed_only_when_the_model_is_set(self, monkeypatch):
        monkeypatch.setattr(config.settings, "model_reader", "")
        openrouter.rebuild_function_models()
        assert "reader" not in openrouter.OpenRouterClient.FUNCTION_MODELS
        monkeypatch.setattr(config.settings, "model_reader", "vendor/reader")
        openrouter.rebuild_function_models()
        assert openrouter.OpenRouterClient.FUNCTION_MODELS["reader"] == "vendor/reader"
        monkeypatch.setattr(config.settings, "model_reader", "")
        openrouter.rebuild_function_models()

    def test_an_id_without_a_slash_is_refused(self):
        with pytest.raises(ValueError):
            config.Settings(model_reader="nomodel")
