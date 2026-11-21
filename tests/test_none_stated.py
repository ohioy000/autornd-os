"""The "none stated" channel (owner's ruling of 2026-11-21, option C).

Before: an ask the pages read did not answer had one way out, blocked_on, and any blocked ask ended the run
with no answer. On the ATmega328P datasheet, which states no thermal resistance, that blocked twice and
gave an invented 45 degC/W once (X41, three draws), because a model cannot tell "I did not find it" from
"it is not there".

Now: the lookup searches the full text of every page it read in full for the words each ask's answer would
be printed with (knowledge/absence.py), and the grounding carries a proof for each page that has none. The
answer may say "none stated" for an ask only through `not_stated`, and the free check `blocked_on_unmet`
refuses a claim for an ask with no proof, as it refuses a blocked ask: the run ends blocked. Allowing "none
stated" on the model's word was the alternative the owner did not choose, because every thin lookup would
then answer it, confidently and wrongly.

These tests hold, in order: what the lookup makes of the pages it read, the check's rule, the verdict's
field, the prompt (byte-identical unless there is a proof to offer), the workflows that opt in, and the
whole graph end to end.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from autornd import config
from autornd.engine import phases
from autornd.graph.adapter import PhaseRunner
from autornd.graph.checks import get_check
from autornd.graph.spec import load
from autornd.knowledge import research
from autornd.knowledge.absence import Proof, render_proofs
from autornd.knowledge.fetch import Source
from autornd.knowledge.research import Finding, research_gaps, source_records
from autornd.models.verdicts import (
    NOT_STATED_NO_ASK, NOT_STATED_NO_PROOF, ImplementVerdict, normalisations_by_kind,
)
from autornd.routing.openrouter import ModelResponse
from tests.prompt_capture import CALLS, recording_client
from tests.test_recompute_vote import REQUEST as E2E_REQUEST
from tests.test_recompute_vote import _drive, _workflow_router

unmet = get_check("blocked_on_unmet")

WORDS = ["thermal resistance", "junction-to-ambient", "θJA", "°C/W"]
# What the ATmega328P datasheet prints where it states current limits, and none of the words above.
# A datasheet's text has lines; the lookup picks the stretches it hands on from them.
DATASHEET = ("Absolute Maximum Ratings\nDC Current per I/O Pin 40.0 mA\nDC Current VCC and GND Pins "
             "200.0 mA\nOperating Temperature -55°C to +125°C\nStorage Temperature -65°C to +150°C\n") * 40
DATASHEET_URL = "https://example.org/ATmega328P-DS40002061B.pdf"
GAPS = ["The junction-to-ambient thermal resistance of the ATmega328P in the 28-pin PDIP package"]
ASKS = [
    {"number": 1, "quote": "the junction-to-ambient thermal resistance", "kind": "value"},
    {"number": 2, "quote": "list the steps in order", "kind": "step"},
]
STORED_NOTHING = lambda *a, **kw: []   # noqa: E731


@pytest.fixture(autouse=True)
def _no_store(monkeypatch):
    """Research asks the store before it pays for a lookup, and writes what it finds to it; neither
    touches a developer's local store in this suite."""
    monkeypatch.setattr(research, "retrieve", STORED_NOTHING)
    monkeypatch.setattr(research, "ingest_text", lambda *a, **kw: 0)


def serve(monkeypatch, pages):
    """The pages a lookup finds: text by address, or None for a page that could not be read."""
    async def fetch(url):
        text = pages.get(url)
        if text is None:
            return Source(url=url, status="failed", reason="no answer within 60 s (read 40 of 653 pages)")
        return Source(url=url, status="fetched", text=text, fetched_at="2026-11-21T08:00:00Z",
                      sha256="ab" * 32, pages=653 if url.endswith(".pdf") else 0)

    monkeypatch.setattr(research, "fetch_source", fetch)


def lookup_client(urls, words=None, words_error=None):
    """A client whose search names `urls` and whose triage call names `words` for ask 1."""
    client = SimpleNamespace()
    order: list[str] = []

    async def chat(**kwargs):
        order.append("search")
        body = json.dumps({"documents": [{"url": u, "title": "t", "near": ""} for u in urls]})
        return ModelResponse(content=body, model="search/model", prompt_tokens=1, completion_tokens=1,
                             cost=0.0, citations=[])

    async def chat_json(**kwargs):
        order.append("words")
        if words_error is not None:
            raise words_error
        data = {"terms": [{"ask": 1, "any_of": words if words is not None else WORDS}]}
        return data, SimpleNamespace(cost=0.0)

    client.chat = AsyncMock(side_effect=chat)
    client.chat_json = AsyncMock(side_effect=chat_json)
    client.order = order
    return client


@pytest.mark.asyncio
class TestTheLookupMakesTheProof:
    async def test_a_page_read_in_full_with_none_of_the_words_is_a_proof_the_finding_hands_on(
            self, monkeypatch):
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        (finding,) = await research_gaps(lookup_client([DATASHEET_URL]), "the whole request", GAPS,
                                         asks=ASKS)
        (proof,) = finding.proofs
        assert (proof.ask, proof.url, proof.pages, proof.chars) == (1, DATASHEET_URL, 653, len(DATASHEET))
        assert proof.terms == tuple(WORDS)
        out = finding.render()
        assert "Proofs of absence, made by the harness (not a model)" in out
        assert f"- Ask 1: none of " in out and f"in the full text of {DATASHEET_URL} (653 pages" in out
        assert finding.searched == {1: WORDS}

    async def test_a_page_that_prints_one_of_the_words_is_no_proof(self, monkeypatch):
        serve(monkeypatch, {DATASHEET_URL: DATASHEET + " Thermal Resis-\ntance 45 °C/W."})
        (finding,) = await research_gaps(lookup_client([DATASHEET_URL]), "r", GAPS, asks=ASKS)
        assert finding.proofs == [] and "Proofs of absence" not in finding.render()
        assert finding.searched == {1: WORDS}   # what was searched is kept either way

    async def test_a_proof_is_made_for_each_page_that_has_none_and_for_no_other(self, monkeypatch):
        other = "https://example.org/application-note.html"
        serve(monkeypatch, {DATASHEET_URL: DATASHEET, other: DATASHEET + " junction-to-ambient: 45"})
        (finding,) = await research_gaps(lookup_client([DATASHEET_URL, other]), "r", GAPS, asks=ASKS)
        assert [p.url for p in finding.proofs] == [DATASHEET_URL]

    async def test_a_page_that_was_not_read_proves_nothing_and_the_words_are_not_even_asked_for(
            self, monkeypatch):
        """Free before paid: with no page read in full there is nothing to search, so the cheap call that
        names the words is not made. And a page that timed out, read in part, is never 'a page with none
        of the words'."""
        serve(monkeypatch, {DATASHEET_URL: None})
        client = lookup_client([DATASHEET_URL])
        (finding,) = await research_gaps(client, "r", GAPS, asks=ASKS)
        assert finding.proofs == [] and finding.searched == {}
        client.chat_json.assert_not_awaited()

    async def test_the_words_are_asked_for_once_and_after_the_pages_are_read(self, monkeypatch):
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        client = lookup_client([DATASHEET_URL])
        await research_gaps(client, "r", GAPS, asks=ASKS)
        assert client.order == ["search", "words"]

    async def test_given_no_asks_the_lookup_is_what_it_was(self, monkeypatch):
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        client = lookup_client([DATASHEET_URL])
        (finding,) = await research_gaps(client, "r", GAPS)
        client.chat_json.assert_not_awaited()
        assert finding.proofs == [] and finding.searched == {}
        assert "Proofs of absence" not in finding.render()

    async def test_only_asks_a_document_can_state_are_searched_for(self, monkeypatch):
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        client = lookup_client([DATASHEET_URL])
        await research_gaps(client, "r", GAPS, asks=ASKS[1:])      # a step only
        client.chat_json.assert_not_awaited()

    async def test_a_failed_call_for_the_words_leaves_the_lookup_whole(self, monkeypatch):
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        client = lookup_client([DATASHEET_URL], words_error=RuntimeError("the provider refused"))
        (finding,) = await research_gaps(client, "r", GAPS, asks=ASKS)
        assert finding.proofs == [] and finding.quotes and finding.documents

    async def test_too_few_words_is_no_proof(self, monkeypatch):
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        (finding,) = await research_gaps(lookup_client([DATASHEET_URL], words=WORDS[:2]), "r", GAPS,
                                         asks=ASKS)
        assert finding.proofs == []

    async def test_a_finding_recalled_from_the_store_is_never_a_proof(self, monkeypatch):
        """A recalled finding read no page this run, so nothing was searched; an ask it would have
        answered stays blocked, as it is today."""
        monkeypatch.setattr(research, "retrieve", lambda *a, **kw: [
            {"text": "stored", "source": DATASHEET_URL, "tag": research.RESEARCH_TAG, "distance": 0.0}])
        client = lookup_client([DATASHEET_URL])
        (finding,) = await research_gaps(client, "r", GAPS, asks=ASKS)
        assert finding.recalled and finding.proofs == []
        client.chat.assert_not_awaited()
        client.chat_json.assert_not_awaited()

    async def test_a_proof_is_never_stored_as_project_knowledge(self, monkeypatch):
        """Only a passage found in its page is remembered (Ruling D56 (5)); a proof is about one fetch."""
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        kept: list[str] = []
        monkeypatch.setattr(research, "ingest_text", lambda text, **kw: kept.append(text) or 1)
        await research_gaps(lookup_client([DATASHEET_URL]), "r", GAPS, asks=ASKS)
        assert kept and not any("none of" in text or "Proofs of absence" in text for text in kept)


@pytest.mark.asyncio
class TestTheRecords:
    async def test_the_source_record_carries_what_was_searched_and_each_proof(self, monkeypatch):
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        findings = await research_gaps(lookup_client([DATASHEET_URL]), "r", GAPS, asks=ASKS)
        (record,) = source_records(findings)
        assert record["searched"] == {"1": WORDS}
        assert [p["ask"] for p in record["proofs"]] == [1]
        assert record["proofs"][0]["url"] == DATASHEET_URL and record["proofs"][0]["pages"] == 653

    async def test_a_lookup_that_searched_nothing_records_exactly_what_it_did_before(self, monkeypatch):
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        findings = await research_gaps(lookup_client([DATASHEET_URL]), "r", GAPS)
        (record,) = source_records(findings)
        assert "searched" not in record and "proofs" not in record

    async def test_the_grounding_record_the_context_node_keeps_carries_the_proofs(self, monkeypatch):
        from autornd.knowledge.context import _record_lookup
        serve(monkeypatch, {DATASHEET_URL: DATASHEET})
        findings = await research_gaps(lookup_client([DATASHEET_URL]), "r", GAPS, asks=ASKS)
        record: dict = {}
        _record_lookup(record, GAPS, findings, "rendered")
        assert [p["ask"] for p in record["proofs"]] == [1] and record["searched"] == {"1": WORDS}
        plain: dict = {}
        _record_lookup(plain, GAPS, [Finding("q", "a")], "rendered")
        assert "proofs" not in plain and "searched" not in plain


@pytest.mark.asyncio
class TestTheAsksReachTheLookupThroughEveryLayer:
    """The asks node runs before the context node; the lookup that reads the pages is three calls down."""

    @pytest.fixture
    def seen(self, monkeypatch):
        got: dict = {}

        async def spy(client, request, gaps, **kwargs):
            got.update(kwargs)
            return []

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        monkeypatch.setattr(research, "research_gaps", spy)
        return got

    @staticmethod
    def client(blocking):
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({
            "objective": "o", "unknowns": ["the thermal resistance"], "blocking_unknowns": blocking,
            "assumptions": [], "considerations": [],
            "briefing": "b", "gaps": ["the thermal resistance"],
            "blocking_gaps": ["the thermal resistance"]}, None))
        return client

    async def test_the_briefings_lookup_is_given_the_asks(self, seen):
        from autornd.knowledge import context as ctx
        from autornd.models.verdicts import RiskLevel
        await ctx.synthesize_briefing(self.client([]), "the request",
                                      [{"text": "t", "tag": "x", "distance": 0.1}],
                                      risk=RiskLevel.HIGH, asks=ASKS)
        assert seen["asks"] == ASKS

    async def test_the_empty_store_path_lookup_is_given_the_asks(self, seen, monkeypatch):
        from autornd.knowledge import context as ctx
        from autornd.models.verdicts import Domain, RiskLevel
        monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
        monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
        await ctx.build_phase_context("the request", [Domain.HARDWARE], client=self.client(
            ["the thermal resistance"]), risk=RiskLevel.HIGH, asks=ASKS)
        assert seen["asks"] == ASKS

    async def test_the_retrieval_path_hands_them_to_the_briefing(self, monkeypatch):
        from autornd.knowledge import context as ctx
        got: dict = {}

        async def one_query(client, query):
            return [query]

        async def rerank(client, query, candidates, n_results):
            return candidates

        async def brief(client, query, chunks, **kwargs):
            got.update(kwargs)
            return "briefing"

        monkeypatch.setattr(ctx, "expand_queries", one_query)
        monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [
            {"text": "t", "tag": "x", "distance": 0.1, "source": "s"}])
        monkeypatch.setattr(ctx, "rerank_chunks", rerank)
        monkeypatch.setattr(ctx, "synthesize_briefing", brief)
        await ctx.load_retrieval_context("the request", client=None, asks=ASKS)
        assert got["asks"] == ASKS

    async def test_build_phase_context_hands_them_to_the_retrieval_path(self, monkeypatch):
        from autornd.knowledge import context as ctx
        from autornd.models.verdicts import Domain
        got: dict = {}

        async def retrieval(query, **kwargs):
            got.update(kwargs)
            return "retrieved"

        monkeypatch.setattr(ctx, "load_retrieval_context", retrieval)
        monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
        await ctx.build_phase_context("the request", [Domain.HARDWARE], asks=ASKS)
        assert got["asks"] == ASKS

    async def test_with_no_asks_the_lookup_is_given_none(self, seen, monkeypatch):
        from autornd.knowledge import context as ctx
        from autornd.models.verdicts import Domain, RiskLevel
        monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
        monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
        await ctx.build_phase_context("the request", [Domain.HARDWARE], client=self.client(
            ["the thermal resistance"]), risk=RiskLevel.HIGH)
        assert seen["asks"] is None


REQUEST = ("Give the junction-to-ambient thermal resistance of the part, and list the steps in order")


def check(blocked_on=(), not_stated=(), proven=(1,), asks=ASKS):
    return unmet(blocked_on=list(blocked_on), asks=asks, request=REQUEST,
                 not_stated=list(not_stated), proven=list(proven))


class TestTheCheckAllowsNoneStatedOnlyWithAProof:
    def test_a_claim_for_an_ask_with_a_proof_is_accepted_and_recorded(self):
        result = check(not_stated=[{"ask": 1, "why": "the datasheet prints no thermal figure"}])
        assert result.passed is True
        assert result.data["blocked"] == []
        assert result.data["none_stated"] == [{"ask": 1, "why": "the datasheet prints no thermal figure"}]
        assert "proof of absence for ask 1" in result.detail

    def test_a_claim_for_an_ask_with_no_proof_ends_the_run_blocked_as_a_blocked_ask_does(self):
        before = normalisations_by_kind().get(NOT_STATED_NO_PROOF, 0)
        result = check(not_stated=[{"ask": 1, "why": "I could not find it"}], proven=[])
        assert result.passed is False and result.data["none_stated"] == []
        (blocked,) = result.data["blocked"]
        assert blocked["ask"] == 1 and "no proof of absence" in blocked["why"]
        assert "I could not find it" in blocked["why"]
        assert result.detail.startswith("implementation names an ask it cannot satisfy: ask 1:")
        assert normalisations_by_kind().get(NOT_STATED_NO_PROOF, 0) == before + 1

    def test_a_proof_for_another_ask_is_no_proof_for_this_one(self):
        result = check(not_stated=[{"ask": 2, "why": "x"}], proven=[1])
        assert result.passed is False and result.data["blocked"][0]["ask"] == 2

    def test_a_boolean_in_the_proofs_is_no_proof_for_ask_one(self):
        """True equals 1 in Python, so a stray boolean among the proven asks would prove ask 1."""
        result = check(not_stated=[{"ask": 1, "why": "x"}], proven=[True])
        assert result.passed is False and result.data["blocked"][0]["ask"] == 1

    def test_a_claim_by_the_asks_own_quote_names_that_ask(self):
        result = check(not_stated=[{"ask": "the junction-to-ambient thermal resistance", "why": "x"}])
        assert result.passed is True and result.data["none_stated"][0]["ask"] == 1

    def test_a_claim_whose_quote_is_none_of_the_asks_names_no_ask_and_is_a_note(self):
        before = normalisations_by_kind().get(NOT_STATED_NO_ASK, 0)
        result = check(not_stated=[{"ask": "give the junction-to-ambient thermal", "why": "x"}])
        assert result.passed is True and result.data["none_stated"] == []
        assert normalisations_by_kind().get(NOT_STATED_NO_ASK, 0) == before + 1

    @pytest.mark.parametrize("named", [0, 3, 99, True, None])
    def test_a_claim_naming_no_ask_is_a_note_counted_and_routed_nowhere(self, named):
        before = normalisations_by_kind().get(NOT_STATED_NO_ASK, 0)
        result = check(not_stated=[{"ask": named, "why": "x"}])
        assert result.passed is True and result.data["none_stated"] == []
        assert normalisations_by_kind().get(NOT_STATED_NO_ASK, 0) == before + 1

    def test_a_bare_string_names_no_ask(self):
        result = check(not_stated=["none stated"])
        assert result.passed is True and result.data["none_stated"] == []

    def test_a_blocked_ask_is_still_blocked_even_when_it_has_a_proof(self):
        """The model chooses its channel: a proof allows 'none stated', it does not rewrite a refusal."""
        result = check(blocked_on=[{"ask": 1, "why": "cannot answer"}], proven=[1])
        assert result.passed is False
        assert result.data["blocked"] == [{"ask": 1, "why": "cannot answer"}]

    def test_one_unproven_claim_blocks_the_run_though_another_is_proven(self):
        asks = [{"number": 1, "quote": "the junction-to-ambient thermal resistance", "kind": "value"},
                {"number": 2, "quote": "the maximum power dissipation", "kind": "value"}]
        result = check(not_stated=[{"ask": 1, "why": "a"}, {"ask": 2, "why": "b"}], proven=[1], asks=asks)
        assert result.passed is False
        assert [b["ask"] for b in result.data["blocked"]] == [2]
        assert [n["ask"] for n in result.data["none_stated"]] == [1]

    def test_no_entry_and_no_claim_reads_as_it_always_did(self):
        result = unmet(blocked_on=[], asks=ASKS, request=REQUEST)
        assert result.passed is True and result.detail == "nothing blocked on"

    def test_a_caller_that_passes_neither_new_argument_is_checked_as_before(self):
        result = unmet(blocked_on=[{"ask": 1, "why": "w"}], asks=ASKS, request=REQUEST)
        assert result.passed is False and result.data["blocked"] == [{"ask": 1, "why": "w"}]

    def test_an_entry_that_names_no_ask_and_no_claim_keeps_its_detail(self):
        result = unmet(blocked_on=["no source"], asks=ASKS, request=REQUEST)
        assert result.passed is True
        assert result.detail == "no blocked entry names an ask — the fold will judge them"


class TestTheVerdictField:
    BASE = {"done": True, "green": True, "summary": "s"}

    def test_a_verdict_without_the_field_parses_as_every_recorded_verdict_does(self):
        assert ImplementVerdict(**self.BASE).not_stated == []

    def test_a_null_is_no_claim(self):
        assert ImplementVerdict(**self.BASE, not_stated=None).not_stated == []

    def test_an_entry_has_the_shape_a_blocked_on_entry_has(self):
        verdict = ImplementVerdict(**self.BASE, not_stated=[{"ask": 1, "why": "w"}, 2, "a sentence"])
        assert [(e.ask, e.why) for e in verdict.not_stated] == [(1, "w"), (2, ""), (None, "a sentence")]

    def test_blocked_on_is_a_field_of_its_own(self):
        verdict = ImplementVerdict(**self.BASE, blocked_on=[{"ask": 3, "why": "w"}],
                                   not_stated=[{"ask": 1, "why": "w"}])
        assert [e.ask for e in verdict.blocked_on] == [3] and [e.ask for e in verdict.not_stated] == [1]


async def implement_prompt(**kwargs):
    """The prompt run_implement sends, through the capture double that bills nothing."""
    CALLS.clear()
    client = recording_client()
    from autornd.specialists.registry import get_specialists
    await phases.run_implement(client, "Give the thermal resistance.", None, get_specialists(["lead"]),
                               iteration=1, context="grounding", asks=[ASKS[0]], results=True, **kwargs)
    (call,) = [c for c in CALLS if c["user"].startswith("Produce the answer")]
    CALLS.clear()
    return call["user"]


BLOCKED_ON_SENTENCE = ("If an ask cannot be honestly answered with the grounding available, name it by "
                       "its number in blocked_on rather than producing something that answers it on paper.")


@pytest.mark.asyncio
class TestThePromptOffersTheChannelOnlyWhereThereIsAProofToOfferIt:
    async def test_with_a_proof_the_instruction_and_the_field_are_there(self):
        prompt = await implement_prompt(proven=[1])
        assert "The grounding holds a proof of absence for ask 1:" in prompt
        assert "list the ask in not_stated" in prompt and "give no figure for it" in prompt
        assert "An ask with no proof of absence is never listed in not_stated" in prompt
        assert "- not_stated: list of the asks the page states none for" in prompt

    async def test_the_ruled_blocked_on_sentence_is_untouched_and_comes_first(self):
        prompt = await implement_prompt(proven=[1])
        sentence = prompt.index(BLOCKED_ON_SENTENCE)
        assert prompt.index("The grounding holds a proof of absence") > sentence
        assert prompt.count(BLOCKED_ON_SENTENCE) == 1

    async def test_the_asks_are_named_by_their_numbers_in_order_once(self):
        prompt = await implement_prompt(proven=[3, 1, 3, True])
        assert "proof of absence for ask 1, 3:" in prompt

    async def test_a_boolean_is_no_ask_number(self):
        assert await implement_prompt(proven=[True]) == await implement_prompt()

    async def test_without_a_proof_the_prompt_is_byte_identical_to_what_it_was(self):
        plain = await implement_prompt()
        assert await implement_prompt(proven=[]) == plain
        assert "not_stated" not in plain and "proof of absence" not in plain

    async def test_the_contract_line_sits_after_blocked_on_and_before_iteration(self):
        prompt = await implement_prompt(proven=[1])
        assert (prompt.index("- blocked_on:") < prompt.index("- not_stated:")
                < prompt.index("- iteration:"))


class TestTheWorkflowsThatOptIn:
    def test_the_default_and_verify_first_opt_in_on_their_context_node_and_no_other_does(self):
        """The lookup is given the asks only where the context node says so. full-team's file is pinned
        byte for byte as the graph arm E ran (D55 (2), tests/test_workflow_choice.py), so it has no such
        arg: its grounding, its cost and its prompt read as they always did, and it still blocks on an ask
        it cannot answer."""
        import glob
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        gated, opting_in = [], []
        for path in sorted(glob.glob(str(root / "workflows" / "*.yaml"))):
            spec = load(path)
            if any(n.kind == "check" and n.check == "blocked_on_unmet" for n in spec.nodes):
                gated.append(Path(path).stem)
            if any(n.kind == "check" and n.check == "build_context" and n.args.get("none_stated")
                   for n in spec.nodes):
                opting_in.append(Path(path).stem)
        assert gated == ["answer-and-recompute", "full-team", "verify-first"]
        assert opting_in == ["answer-and-recompute", "verify-first"]
        assert "none_stated" not in (root / "workflows" / "full-team.yaml").read_text(encoding="utf-8")

    def test_no_implement_node_carries_an_opt_in_of_its_own(self):
        """One switch: a proof exists only where the context node opted in, and a proof is all the
        implement prompt needs."""
        for stem in ("answer-and-recompute", "full-team", "verify-first"):
            node = next(n for n in load(f"workflows/{stem}.yaml").nodes
                        if n.kind == "ai" and n.prompt == "implement")
            assert "none_stated" not in node.args

    def test_the_check_node_declares_no_new_argument(self):
        """The claims and the proofs are read by the adapter, so the shipped workflows and every scripted
        double that drives them are checked exactly as before."""
        for stem in ("answer-and-recompute", "full-team", "verify-first"):
            node = next(n for n in load(f"workflows/{stem}.yaml").nodes if n.id == "blocked_check")
            assert set(node.args) == {"blocked_on", "asks", "request"}


class TestTheAdapterReadsTheProvenAsks:
    """What the context node left in the state is all the implement step and the check have to go on,
    and only ask numbers in it count."""

    @staticmethod
    def proven(outputs):
        return PhaseRunner._proven_asks(None, SimpleNamespace(outputs=outputs))

    def test_the_numbers_the_context_node_recorded_are_read(self):
        assert self.proven({"context": {"proven": [2, 1]}}) == [2, 1]

    def test_only_ask_numbers_count(self):
        assert self.proven({"context": {"proven": [True, 2, "3", None, 1.5]}}) == [2]

    def test_no_record_or_one_that_is_not_a_mapping_is_no_proof(self):
        assert self.proven({}) == []
        assert self.proven({"context": "grounding text"}) == []
        assert self.proven({"context": {"proven": None}}) == []
        assert self.proven({"context": {}}) == []


@pytest.mark.asyncio
class TestTheAdapterReadsTheClaimsWhicheverShapeTheAnswerHas:
    """`implement` is a verdict in a run and a plain mapping in the doubles that stand in for it. The
    adapter reads the claims and the proofs, so the shipped workflows declare nothing new."""

    CLAIM = [{"ask": 1, "why": "the datasheet prints none"}]

    @staticmethod
    async def run(implement, proven=(1,)):
        from autornd.graph.executor import ExecutionState
        from autornd.graph.spec import Node, NodeKind
        from autornd.routing.openrouter import OpenRouterClient

        runner = PhaseRunner(OpenRouterClient(api_key="test"))
        state = ExecutionState(request=REQUEST, iteration=1)
        state.outputs["implement"] = implement
        state.outputs["asks_anchored"] = {"anchored": ASKS, "quotes": [a["quote"] for a in ASKS],
                                          "demoted": []}
        state.outputs["context"] = {"proven": list(proven)}
        node = Node(id="blocked_check", kind=NodeKind.CHECK, check="blocked_on_unmet",
                    args={"blocked_on": "implement.blocked_on", "asks": "asks_anchored.anchored",
                          "request": "request"})
        return await runner.run_check(node, state)

    def answers(self):
        return (ImplementVerdict(done=True, green=True, summary="s", iteration=1, not_stated=self.CLAIM),
                {"blocked_on": [], "not_stated": self.CLAIM, "summary": "s"})

    async def test_a_claim_on_a_verdict_is_read(self):
        result = await self.run(self.answers()[0])
        assert result.passed is True and result.data["none_stated"] == self.CLAIM

    async def test_a_claim_in_a_plain_mapping_is_read(self):
        result = await self.run(self.answers()[1])
        assert result.passed is True and result.data["none_stated"] == self.CLAIM

    async def test_a_claim_with_no_proof_blocks_whichever_shape_the_answer_has(self):
        for implement in self.answers():
            result = await self.run(implement, proven=())
            assert result.passed is False and result.data["none_stated"] == []


def _fake_grounding(proofs, seen):
    """The context node's lookup, as if the pages had been read: the proofs in its record and in its text.
    As the real lookup does, it makes proofs only when it is given the asks."""
    async def build(request, domains, specialists=None, **kwargs):
        seen.update(kwargs)
        made = list(proofs) if kwargs.get("asks") else []
        kwargs["grounding_lookup"].update({"asked": [request], "found": 1, "findings": "…",
                                           "proofs": [p.as_record() for p in made]})
        return "=== RESEARCHED FACTS ===\n" + "\n".join(render_proofs(made))
    return build


PROOF = Proof(ask=1, terms=("cap", "ceiling", "maximum delay"), url=DATASHEET_URL, chars=1000, pages=653,
              fetched_at="2026-11-21T08:00:00Z", sha256="3f2a9c1d77be" + "0" * 52)


def _answering(**fields):
    """answer-and-recompute's double whose answer states ask 2 and, for ask 1, whatever `fields` say."""
    route = _workflow_router(60.0, [60.0] * 3)

    def router(user_message, calls):
        data = route(user_message, calls)
        if user_message.startswith("Produce the answer to the following request"):
            data = dict(data, results=[{"ask": 2, "value": "yes", "unit": ""}], **fields)
        return data
    return router


@pytest.mark.asyncio
class TestTheWholeGraphEndToEnd:
    """workflows/answer-and-recompute.yaml behind the double, with the grounding's lookup stood in for."""

    async def test_an_ask_with_a_proof_is_answered_none_stated_and_the_run_completes(self, monkeypatch):
        seen: dict = {}
        monkeypatch.setattr("autornd.graph.adapter.build_phase_context", _fake_grounding([PROOF], seen))
        router = _answering(not_stated=[{"ask": 1, "why": "the datasheet prints none"}])
        state, _, calls = await _drive(load("workflows/answer-and-recompute.yaml"), router, E2E_REQUEST)
        assert state.status == "completed"
        assert state.outputs["blocked_check"]["none_stated"] == [
            {"ask": 1, "why": "the datasheet prints none"}]
        assert state.outputs["context"]["proven"] == [1]
        # The lookup was given the run's anchored asks, numbered as the answer step reads them.
        assert [a["number"] for a in seen["asks"]] == [1, 2] and seen["asks"][0]["kind"] == "value"
        # And the answer step was offered the channel, naming the ask.
        (answer,) = [c for c in calls if c["user"].startswith("Produce the answer")]
        assert "The grounding holds a proof of absence for ask 1:" in answer["user"]

    async def test_the_same_claim_with_no_proof_ends_the_run_blocked(self, monkeypatch):
        seen: dict = {}
        monkeypatch.setattr("autornd.graph.adapter.build_phase_context", _fake_grounding([], seen))
        router = _answering(not_stated=[{"ask": 1, "why": "I could not find it"}])
        state, runner, calls = await _drive(load("workflows/answer-and-recompute.yaml"), router,
                                            E2E_REQUEST)
        assert state.status == "blocked"
        assert state.reason.startswith("Implementation blocked on an ask it cannot satisfy")
        assert "ask 1: none stated, claimed with no proof of absence" in state.reason
        # No proof, so the answer step was never offered the channel.
        (answer,) = [c for c in calls if c["user"].startswith("Produce the answer")]
        assert "not_stated" not in answer["user"]
        assert state.outputs["context"]["proven"] == []

    async def test_a_proof_for_another_ask_does_not_allow_the_claim(self, monkeypatch):
        monkeypatch.setattr("autornd.graph.adapter.build_phase_context", _fake_grounding([PROOF], {}))
        router = _answering(not_stated=[{"ask": 2, "why": "none"}])
        state, _, _ = await _drive(load("workflows/answer-and-recompute.yaml"), router, E2E_REQUEST)
        assert state.status == "blocked"

    async def test_an_ask_blocked_on_stays_blocked_though_it_has_a_proof(self, monkeypatch):
        monkeypatch.setattr("autornd.graph.adapter.build_phase_context", _fake_grounding([PROOF], {}))
        router = _answering(blocked_on=[{"ask": 1, "why": "cannot answer"}])
        state, _, _ = await _drive(load("workflows/answer-and-recompute.yaml"), router, E2E_REQUEST)
        assert state.status == "blocked"

    async def test_a_run_with_no_lookup_and_no_claim_completes_as_it_always_did(self, monkeypatch):
        seen: dict = {}
        monkeypatch.setattr("autornd.graph.adapter.build_phase_context", _fake_grounding([], seen))
        state, _, calls = await _drive(load("workflows/answer-and-recompute.yaml"),
                                       _workflow_router(60.0, [60.0] * 3), E2E_REQUEST)
        assert state.status == "completed" and state.outputs["blocked_check"]["none_stated"] == []
        (answer,) = [c for c in calls if c["user"].startswith("Produce the answer")]
        assert "not_stated" not in answer["user"]

    async def test_a_context_node_that_does_not_opt_in_gives_the_lookup_no_asks_and_the_answer_no_channel(
            self, monkeypatch):
        seen: dict = {}
        monkeypatch.setattr("autornd.graph.adapter.build_phase_context", _fake_grounding([PROOF], seen))
        spec = load("workflows/answer-and-recompute.yaml")
        next(n for n in spec.nodes if n.id == "context").args.pop("none_stated")
        state, _, calls = await _drive(spec, _answering(), E2E_REQUEST)
        assert seen["asks"] is None
        (answer,) = [c for c in calls if c["user"].startswith("Produce the answer")]
        assert "not_stated" not in answer["user"] and "proof of absence" not in answer["user"]
        assert state.status == "completed" and state.outputs["context"]["proven"] == []
