"""Ruling D56: a finding is checked against its source.

A lookup's reply is typed: an answer, and the passages it rests on, each with
its page's address. The harness fetches each page, records which version it
read, and looks for each passage in it. An answer whose passage is found is
checked; a question whose quoted passage is not found is asked once more; what
is still not found is marked unverified. Only a found passage is kept for
later runs.

Every page here is served by an httpx.MockTransport and every name resolves
through a stub: the suite never reaches the network.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from autornd import config
from autornd.knowledge import fetch, research
from autornd.knowledge.research import (
    AGAIN_PROMPT, MIN_QUOTE_CHARS, RESEARCH_TAG, Finding, Quote, quote_found,
    render_findings, research_gaps,
)
from autornd.routing.openrouter import ModelResponse

PAGE = "https://standards.example.org/868"
OTHER = "https://datasheets.example.com/cell"
PASSAGE = "The maximum radiated power in this band is 25 mW e.r.p."
HTML = (
    "<html><head><title>868 MHz</title><style>p {color: red}</style>"
    "<script>var limit = '500 mW';</script></head><body>"
    "<h1>Short range devices</h1><p>The maximum radiated power in this band "
    "is 25&nbsp;mW <b>e.r.p.</b></p><p>Duty cycle: 1&#37;.</p></body></html>"
)
CELL = "Charge each cell to 3.65 V and no higher, at 25 C."


def _served(pages: dict[str, tuple[int, dict[str, str], bytes]], seen=None):
    """A transport serving `pages`, keyed by address, recording each GET.

    The fetch connects to the checked address and names the page in the
    Host header (D56, amended), so the address a page is served under is
    rebuilt from that header."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url.copy_with(netloc=request.headers["host"].encode()))
        if seen is not None:
            seen.append(url)
        status, headers, body = pages.get(url, (404, {}, b"not here"))
        return httpx.Response(status, headers=headers, content=body)
    return httpx.MockTransport(handler)


def _html(body: str = HTML, **headers: str) -> tuple[int, dict[str, str], bytes]:
    return 200, {"content-type": "text/html; charset=utf-8", **headers}, body.encode()


def _text(body: str) -> tuple[int, dict[str, str], bytes]:
    return 200, {"content-type": "text/plain"}, body.encode()


def _pdf(text: str) -> tuple[int, dict[str, str], bytes]:
    """A one-page PDF whose text layer is `text` (empty: a page with none)."""
    stream = (f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
              if text else b"")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, xref))
    return 200, {"content-type": "application/pdf"}, bytes(out)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Names resolve to a public documentation address, the store is empty
    and records nothing, and the search tier is configured."""
    async def public(host):
        return ["93.184.216.34"]

    monkeypatch.setattr(fetch, "_addresses", public)
    monkeypatch.setattr(fetch, "_transport", _served({}))
    monkeypatch.setattr(research, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(research, "ingest_text", lambda *a, **k: 0)
    monkeypatch.setattr(config.settings, "model_search", "vendor/search")
    research.reset_untyped_replies()
    research.reset_dropped_quotes()
    yield
    research.reset_untyped_replies()
    research.reset_dropped_quotes()


def _reply(answer: str = "25 mW e.r.p.", quotes=(), citations=(PAGE,)) -> ModelResponse:
    content = json.dumps({"answer": answer, "quotes": [
        {"question": n, "text": text, "url": url} for n, text, url in quotes]})
    return ModelResponse(content=content, model="search/model", prompt_tokens=10,
                         completion_tokens=20, cost=0.005, citations=list(citations))


def _client(*replies: ModelResponse):
    client = AsyncMock()
    client.chat = AsyncMock(side_effect=list(replies))
    return client


class TestTheReplyIsTyped:
    async def test_the_answer_and_its_quotes_are_fields(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        client = _client(_reply(quotes=[(1, PASSAGE, PAGE)]))
        finding, = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert finding.answer == "25 mW e.r.p."
        assert [(q.question, q.text, q.url) for q in finding.quotes] == [(1, PASSAGE, PAGE)]
        assert client.chat.await_args.kwargs["function"] == "search"
        assert client.chat_json.await_count == 0, "the lookup stays a plain chat"

    @pytest.mark.parametrize("content", [
        "25 mW e.r.p., per ETSI EN 300 220.",
        '{"figure": "25 mW"}',
    ])
    async def test_a_reply_not_in_the_format_is_kept_whole_and_counted(self, content):
        client = _client(ModelResponse(content=content, model="m", prompt_tokens=1,
                                       completion_tokens=1, cost=0.0, citations=[PAGE]))
        finding, = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert finding.answer == content
        assert finding.quotes == [] and finding.unchecked() == [1]
        assert research.untyped_replies() == 1
        assert client.chat.await_count == 1, "nothing quoted, so nothing asked again"


class TestTheFetch:
    async def test_a_fetch_records_the_version_it_read(self, monkeypatch):
        body = HTML.encode()
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(
            **{"last-modified": "Tue, 01 Oct 2026 00:00:00 GMT", "etag": '"v7"'})}))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "fetched" and source.final_url == PAGE
        assert source.sha256 == hashlib.sha256(body).hexdigest()
        assert source.last_modified == "Tue, 01 Oct 2026 00:00:00 GMT"
        assert source.etag == '"v7"' and source.content_type == "text/html"
        assert len(source.fetched_at) == 20 and source.fetched_at.endswith("Z")

    async def test_html_is_read_as_the_text_a_reader_sees(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        text = (await fetch.fetch_source(PAGE)).text
        assert "500 mW" not in text and "color: red" not in text
        assert "Duty cycle: 1%." in text
        assert quote_found(PASSAGE, text)

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.org/x",
                                     "gopher://example.org/", "https:///no-host"])
    async def test_only_a_web_address_with_a_host_is_fetched(self, monkeypatch, url):
        seen: list[str] = []
        monkeypatch.setattr(fetch, "_transport", _served({}, seen))
        source = await fetch.fetch_source(url)
        assert source.status == "refused" and seen == []

    @pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "192.168.1.1",
                                         "169.254.169.254", "::1", "fd00::1"])
    async def test_a_name_on_a_private_network_is_refused(self, monkeypatch, address):
        async def private(host):
            return ["93.184.216.34", address]

        seen: list[str] = []
        monkeypatch.setattr(fetch, "_addresses", private)
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}, seen))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "refused" and address in source.reason
        assert seen == [], "nothing was requested"

    async def test_every_redirect_is_checked_like_the_first(self, monkeypatch):
        async def resolve(host):
            return ["127.0.0.1"] if host == "internal.example" else ["93.184.216.34"]

        seen: list[str] = []
        monkeypatch.setattr(fetch, "_addresses", resolve)
        monkeypatch.setattr(fetch, "_transport", _served({
            PAGE: (302, {"location": "http://internal.example/admin"}, b"")}, seen))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "refused"
        assert source.final_url == "http://internal.example/admin"
        assert seen == [PAGE]

    async def test_a_redirect_to_a_public_page_is_followed(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({
            PAGE: (301, {"location": "/868-v2"}, b""),
            PAGE + "-v2": _html()}))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "fetched" and source.final_url == PAGE + "-v2"

    async def test_redirects_are_bounded(self, monkeypatch):
        loop = {f"{PAGE}/{n}": (302, {"location": f"{PAGE}/{n + 1}"}, b"")
                for n in range(10)}
        seen: list[str] = []
        monkeypatch.setattr(fetch, "_transport", _served(loop, seen))
        source = await fetch.fetch_source(f"{PAGE}/0")
        assert source.status == "failed" and "redirects" in source.reason
        assert len(seen) == fetch.MAX_REDIRECTS + 1

    @pytest.mark.parametrize("served, reason", [
        ((404, {}, b"gone"), "HTTP 404"),
        ((200, {"content-type": "application/zip"}, b"PK"),
         "content type application/zip is not read as text"),
        ((200, {"content-type": "text/plain"}, b"x" * (fetch.FETCH_MAX_BYTES + 1)),
         f"larger than {fetch.FETCH_MAX_BYTES} bytes"),
    ])
    async def test_a_page_that_cannot_be_read_says_why(self, monkeypatch, served, reason):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: served}))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed" and source.reason == reason

    async def test_a_slow_page_is_given_up_on(self, monkeypatch):
        async def slow(request):
            await asyncio.sleep(1.0)
            return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"x")

        monkeypatch.setattr(fetch, "FETCH_TIMEOUT_SECONDS", 0.05)
        monkeypatch.setattr(fetch, "_transport", httpx.MockTransport(slow))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed" and source.reason == "no answer within 0.05 s"

    async def test_a_fetch_never_raises(self, monkeypatch):
        def broken(request):
            raise httpx.ConnectError("refused by the far end")

        monkeypatch.setattr(fetch, "_transport", httpx.MockTransport(broken))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed" and "ConnectError" in source.reason


class TestTheQuoteCheck:
    @pytest.mark.parametrize("quote", [
        PASSAGE,
        "  the MAXIMUM radiated power in this band\nis 25 mW e.r.p.  ",
        "\u201cThe maximum radiated power in this band is 25\u00a0mW e.r.p.\u201d",
    ])
    def test_spacing_case_and_quote_marks_are_read_alike(self, quote):
        page = "Short range devices\nThe maximum radiated power in this band is 25 mW e.r.p.\n"
        assert quote_found(quote, page)

    @pytest.mark.parametrize("quote", [
        "The maximum radiated power in this band is 25 mW e.i.r.p.",
        "The maximum power in this band is 25 mW e.r.p.",
        "The maximum radiated power ... is 25 mW e.r.p.",
    ])
    def test_a_changed_or_missing_word_is_not_found(self, quote):
        assert not quote_found(quote, PASSAGE)

    def test_a_short_quote_checks_nothing(self):
        assert len("25 mW e.r.p.") < MIN_QUOTE_CHARS
        assert not quote_found("25 mW e.r.p.", PASSAGE)

    async def test_a_found_passage_checks_its_answer(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        finding, = await research_gaps(
            _client(_reply(quotes=[(1, PASSAGE, PAGE)])), "a radio", ["The EU 868 MHz limit"])
        quote, = finding.quotes
        assert quote.status == "found" and finding.checked() == {1}
        assert quote.sha256 == hashlib.sha256(HTML.encode()).hexdigest()
        rendered = finding.render()
        assert f'- [1] "{PASSAGE}" — {PAGE} (fetched {quote.fetched_at}, sha256 {quote.sha256[:12]})' in rendered
        assert "unverified" not in rendered

    @pytest.mark.parametrize("served, status", [
        (_html("<p>A different page entirely, about something else.</p>"), "not_found"),
        ((200, {"content-type": "application/pdf"}, b"%PDF"), "unfetched"),
    ])
    async def test_a_passage_not_found_leaves_its_answer_unverified(
            self, monkeypatch, served, status):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: served}))
        monkeypatch.setattr(research, "MAX_ROUNDS", 1)
        finding, = await research_gaps(
            _client(_reply(quotes=[(1, PASSAGE, PAGE)])), "a radio", ["The EU 868 MHz limit"])
        assert finding.quotes[0].status == status and finding.unchecked() == [1]
        assert "No quoted passage was found in its page — treat this answer as unverified." in finding.render()

    async def test_a_bundle_names_the_questions_left_unverified(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(), OTHER: _text(CELL)}))
        finding, = await research_gaps(_client(_reply(quotes=[
            (1, PASSAGE, PAGE), (2, "Charge each cell to 3.60 V and no higher.", OTHER)])),
            "a radio", ["The EU 868 MHz limit", "The LiFePO4 cutoff", "The duty cycle"])
        assert finding.checked() == {1} and finding.unchecked() == [2, 3]
        assert ("No quoted passage was found in its page for questions 2, 3 — treat "
                "those answers as unverified.") in finding.render()

    async def test_pages_fetched_per_lookup_are_bounded(self, monkeypatch):
        seen: list[str] = []
        pages = {f"{PAGE}/{n}": _text(PASSAGE) for n in range(fetch.MAX_FETCHES + 1)}
        monkeypatch.setattr(fetch, "_transport", _served(pages, seen))
        finding, = await research_gaps(_client(_reply(quotes=[
            (1, PASSAGE, url) for url in pages])), "a radio", ["The EU 868 MHz limit"])
        assert len(seen) == fetch.MAX_FETCHES
        assert [q.status for q in finding.quotes][-1] == "unfetched"
        assert finding.quotes[-1].reason == f"past the {fetch.MAX_FETCHES}-page fetch cap"


class TestAskedOnceMore:
    async def test_a_passage_not_found_is_asked_again_once(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(), OTHER: _text(CELL)}))
        client = _client(
            _reply(quotes=[(1, PASSAGE, PAGE), (2, "Charge to 4.2 V per cell, always.", OTHER)]),
            _reply(answer="3.65 V", quotes=[(1, CELL, OTHER)]))
        first, second = await research_gaps(
            client, "a radio", ["The EU 868 MHz limit", "The LiFePO4 cutoff"])
        assert client.chat.await_count == 2
        again = client.chat.await_args_list[1].kwargs["user_message"]
        assert AGAIN_PROMPT.format(questions="The LiFePO4 cutoff") in again
        assert "The EU 868 MHz limit" not in again, "a checked question is not asked again"
        assert (second.round, second.asked, second.checked()) == (2, ["The LiFePO4 cutoff"], {1})
        assert second.render().startswith("Q (asked again): The LiFePO4 cutoff")
        assert first.unchecked() == [2]

    async def test_a_reply_that_quoted_nothing_is_not_asked_again(self):
        client = _client(_reply(quotes=[]))
        finding, = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert client.chat.await_count == 1 and finding.unchecked() == [1]

    async def test_there_is_no_third_round(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html("<p>Nothing here at all.</p>")}))
        client = _client(_reply(quotes=[(1, PASSAGE, PAGE)]),
                         _reply(quotes=[(1, PASSAGE, PAGE)]))
        findings = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert client.chat.await_count == 2 and [f.round for f in findings] == [1, 2]

    async def test_every_answer_found_costs_one_request(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        client = _client(_reply(quotes=[(1, PASSAGE, PAGE)]))
        await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert client.chat.await_count == 1


class TestOnlyAFoundPassageIsKept:
    async def test_each_found_passage_is_stored_under_its_own_page(self, monkeypatch):
        stored: list[tuple[str, str, str]] = []
        monkeypatch.setattr(research, "ingest_text",
                            lambda text, tag, source="": stored.append((text, tag, source)))
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(), OTHER: _text(CELL)}))
        monkeypatch.setattr(research, "MAX_ROUNDS", 1)
        await research_gaps(_client(_reply(quotes=[
            (1, PASSAGE, PAGE), (2, CELL, OTHER), (3, "Not on the page, this sentence.", PAGE)])),
            "a radio", ["The EU 868 MHz limit", "The LiFePO4 cutoff", "The duty cycle"])
        assert [(tag, source) for _, tag, source in stored] == [
            (RESEARCH_TAG, PAGE), (RESEARCH_TAG, OTHER)]
        text = stored[1][0]
        assert text.startswith(f'Q: The LiFePO4 cutoff\nThe page says: "{CELL}"\nPage: {OTHER} (fetched ')
        assert hashlib.sha256(CELL.encode()).hexdigest() in text

    async def test_only_checked_material_is_recalled(self, monkeypatch):
        seen = {}

        def fake_retrieve(query, n_results=1, where=None):
            seen["where"] = where
            return []

        monkeypatch.setattr(research, "retrieve", fake_retrieve)
        await research_gaps(_client(_reply()), "a radio", ["The EU 868 MHz limit"])
        assert seen["where"] == {"tag": "research-quoted"}

    @pytest.mark.parametrize("distance, reused", [(0.1, True), (0.2, False)])
    async def test_only_a_near_restatement_is_reused(self, monkeypatch, distance, reused):
        """Cosine distance: the old 0.35 squared-L2 intent is 0.175 here."""
        monkeypatch.setattr(research, "retrieve", lambda *a, **k: [{
            "text": f'Q: The EU 868 MHz limit\nThe page says: "{PASSAGE}"',
            "source": PAGE, "tag": RESEARCH_TAG, "distance": distance}])
        client = _client(_reply())
        findings = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert (client.chat.await_count == 0) is reused
        assert (findings[0].model == "recalled") is reused

    async def test_a_recalled_passage_is_not_asked_again_or_marked(self, monkeypatch):
        monkeypatch.setattr(research, "retrieve", lambda *a, **k: [{
            "text": f'Q: The EU 868 MHz limit\nThe page says: "{PASSAGE}"',
            "source": PAGE, "tag": RESEARCH_TAG, "distance": 0.05}])
        finding, = await research_gaps(_client(), "a radio", ["The EU 868 MHz limit"])
        assert finding.recalled and finding.unchecked() == []
        assert "unverified" not in render_findings([finding])


class TestTheRecord:
    async def test_the_grounding_record_counts_what_the_check_found(self, monkeypatch):
        import autornd.knowledge.context as ctx
        from autornd.models.verdicts import Domain, RiskLevel

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
        monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        client = _client(
            _reply(quotes=[(1, PASSAGE, PAGE), (2, "Not on the page, this sentence.", PAGE)]),
            _reply(quotes=[(1, "Still not on the page, this one.", PAGE)]))
        client.chat_json = AsyncMock(return_value=({
            "objective": "size it", "unknowns": ["the limit", "the duty cycle"],
            "blocking_unknowns": ["the limit", "the duty cycle"],
            "assumptions": [], "considerations": []}, None))
        record: dict = {}
        out = await ctx.build_phase_context(
            "size a radio", [Domain.HARDWARE], client=client,
            risk=RiskLevel.HIGH, grounding_lookup=record)
        assert record["quotes"] == {"found": 1, "not_found": 2, "unfetched": 0,
                                    "too_short": 0}
        assert record["asked_again"] == 1 and record["found"] == 2
        assert "1 of 2 have answers no passage found in its page backs" not in out
        assert "2 of 2 have answers no passage found in its page backs" in out


def test_a_finding_built_the_old_way_is_one_unverified_question():
    finding = Finding("q", "a", ["https://x/y"])
    assert finding.unchecked() == [1] and finding.to_ask_again() == []
    assert Quote(1, "t", "u").status == "unchecked"


class TestTheFetchConnectsToTheAddressItChecked:
    """D56, amended 2026-10-28: the check resolves the name once a hop, and
    the request goes to the address the check approved. The first version
    let the connection resolve the name again, so a name that answered one
    way to the check and another to the connection got through."""

    async def test_the_request_goes_to_the_checked_address(self, monkeypatch):
        sent: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return httpx.Response(200, headers={"content-type": "text/plain"},
                                  content=PASSAGE.encode())

        monkeypatch.setattr(fetch, "_transport", httpx.MockTransport(handler))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "fetched" and source.final_url == PAGE
        (request,) = sent
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "standards.example.org"
        assert request.extensions["sni_hostname"] == "standards.example.org"

    async def test_nothing_is_taken_from_the_environment(self, monkeypatch):
        """No proxy, which would resolve the name itself, and no .netrc
        credentials. httpx ignores the environment's proxies whenever a test
        transport is set, so the setting is read where the client is made."""
        made: list[dict] = []
        real = httpx.AsyncClient

        def client(*args, **kwargs):
            made.append(kwargs)
            return real(*args, **kwargs)

        monkeypatch.setattr(fetch.httpx, "AsyncClient", client)
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        assert (await fetch.fetch_source(PAGE)).status == "fetched"
        assert [kwargs["trust_env"] for kwargs in made] == [False]


class TestOneBadQuoteCostsOnlyItself:
    """Audit of 2026-11-11: one malformed quote used to void the reply's
    typed reading, so the answer was kept as raw JSON and every good quote
    beside it went unchecked."""

    @pytest.mark.parametrize("bad", [
        {"question": 1, "text": PASSAGE},                 # no address
        {"question": "first", "text": PASSAGE, "url": PAGE},
        {"question": 1, "text": "  ", "url": PAGE},
        "not an object",
    ])
    async def test_the_answer_and_the_good_quotes_are_kept(self, monkeypatch, bad):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        content = json.dumps({"answer": "25 mW e.r.p.", "quotes": [
            bad, {"question": 1, "text": PASSAGE, "url": PAGE}]})
        client = _client(ModelResponse(content=content, model="m", prompt_tokens=1,
                                       completion_tokens=1, cost=0.0, citations=[PAGE]))
        finding, = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert finding.answer == "25 mW e.r.p."
        assert [q.status for q in finding.quotes] == ["found"]
        assert research.dropped_quotes() == 1
        assert research.untyped_replies() == 0

    async def test_quotes_that_are_not_a_list_leave_the_answer(self):
        content = json.dumps({"answer": "25 mW e.r.p.", "quotes": "none"})
        client = _client(ModelResponse(content=content, model="m", prompt_tokens=1,
                                       completion_tokens=1, cost=0.0, citations=[PAGE]))
        finding, = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert finding.answer == "25 mW e.r.p." and finding.quotes == []
        assert research.dropped_quotes() == 1


class TestTheQuoteCheckReadsPastPrinting:
    @pytest.mark.parametrize("quote, page", [
        # The quote ends its sentence where the page goes on.
        ("The maximum radiated power in this band is 25 mW e.r.p.",
         "The maximum radiated power in this band is 25 mW e.r.p, with a 1% duty cycle."),
        # The page carries a reference mark the quote left out.
        ("The maximum radiated power in this band is 25 mW e.r.p.",
         "The maximum radiated power[3] in this band is 25 mW e.r.p."),
        # The page prints a zero-width space inside a word.
        ("The maximum radiated power in this band is 25 mW e.r.p.",
         "The maxi\u200bmum radiated power in this band is 25 mW e.r.p."),
    ])
    def test_a_closing_mark_a_reference_mark_and_a_hidden_character_change_no_word(
            self, quote, page):
        assert quote_found(quote, page)

    def test_a_changed_figure_is_still_not_found(self):
        """Break-proof for the three above: they loosen printing, not words."""
        assert not quote_found(
            "The maximum radiated power in this band is 25 mW e.r.p.",
            "The maximum radiated power[3] in this band is 250 mW e.r.p.")


class TestWhatTheFetchCanRead:
    async def test_a_pdf_is_read_through_its_text_layer(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _pdf(PASSAGE)}))
        finding, = await research_gaps(
            _client(_reply(quotes=[(1, PASSAGE, PAGE)])), "a radio", ["The EU 868 MHz limit"])
        assert finding.quotes[0].status == "found"

    @pytest.mark.parametrize("served, reason", [
        (_pdf(""), "the PDF has no text layer"),
        ((200, {"content-type": "application/pdf"}, b"%PDF-1.7 broken"),
         "the PDF could not be read"),
    ])
    async def test_a_pdf_with_no_text_says_so(self, monkeypatch, served, reason):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: served}))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed" and source.reason.startswith(reason)

    async def test_a_challenge_page_is_not_a_page_read(self, monkeypatch):
        """ecfr.gov answered HTTP 200 with this on 2026-11-11, and the quote
        was recorded "not found in the page" when no page had been read."""
        wall = _html("<html><body><h1>Request Access</h1><p>Please complete "
                     "the CAPTCHA to continue.</p></body></html>")
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: wall}))
        monkeypatch.setattr(research, "MAX_ROUNDS", 1)
        finding, = await research_gaps(
            _client(_reply(quotes=[(1, PASSAGE, PAGE)])), "a radio", ["The EU 868 MHz limit"])
        quote, = finding.quotes
        assert quote.status == "unfetched" and "challenge page" in quote.reason

    def test_a_long_page_that_names_a_captcha_is_a_page(self):
        assert fetch.challenge_page("Request Access")
        assert not fetch.challenge_page(
            "This standard covers CAPTCHA design. " + "word " * 1000)

    async def test_an_ecfr_section_is_read_through_the_renderer(self, monkeypatch):
        reader = "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-C/section-15.247"
        api = ("https://www.ecfr.gov/api/renderer/v1/content/enhanced/current/"
               "title-47?part=15&section=15.247")
        assert fetch.readable_address(reader) == api
        assert fetch.readable_address(PAGE) == PAGE
        seen: list[str] = []
        monkeypatch.setattr(fetch, "_transport", _served({api: _html()}, seen))
        source = await fetch.fetch_source(reader)
        assert source.status == "fetched" and seen == [api]
        assert source.url == reader and source.final_url == api

    @pytest.mark.parametrize("reader, query", [
        ("https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15",
         "title-47?part=15"),
        ("https://ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-C/",
         "title-47?part=15&subpart=C"),
        ("https://www.ecfr.gov/current/title-29/part-1910#p-1", "title-29?part=1910"),
    ])
    def test_an_ecfr_part_is_read_through_the_renderer(self, reader, query):
        """Live 2026-11-13: three part-level addresses got the challenge page."""
        assert fetch.readable_address(reader) == (
            "https://www.ecfr.gov/api/renderer/v1/content/enhanced/current/" + query)

    def test_an_address_that_is_not_a_part_or_a_section_is_left_alone(self):
        for url in ("https://www.ecfr.gov/current/title-47",
                    "https://www.ecfr.gov/current/title-47/chapter-I",
                    "https://example.org/current/title-47/part-15"):
            assert fetch.readable_address(url) == url


class TestTheSourcesAreReturned:
    async def test_a_lookup_record_names_each_page_and_what_was_found(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        monkeypatch.setattr(research, "MAX_ROUNDS", 1)
        findings = await research_gaps(_client(_reply(quotes=[
            (1, PASSAGE, PAGE), (2, "Not on the page, this sentence.", PAGE)])),
            "a radio", ["The EU 868 MHz limit", "The duty cycle"])
        record, = research.source_records(findings)
        assert record["round"] == 1 and record["recalled"] is False
        assert record["citations"] == [PAGE]
        assert record["unverified_questions"] == [2]
        assert [(q["question"], q["url"], q["status"]) for q in record["quotes"]] == [
            (1, PAGE, "found"), (2, PAGE, "not_found")]
        found = record["quotes"][0]
        assert found["text"] == PASSAGE and found["sha256"] and found["fetched_at"]
        # Each quote carries the words of its own question, not the first's.
        assert [q["question_text"] for q in record["quotes"]] == [
            "The EU 868 MHz limit", "The duty cycle"]
        json.dumps(record)   # plain data: it goes through the phase channel


class TestARequestForSourcesIsAlwaysLookedUp:
    """Owner's decision of 2026-11-13, after a live run of 2026-11-12: "Cite
    the datasheet" was triaged low risk, no lookup ran, and the answer gave
    a figure from memory with a quotation its source does not contain."""

    async def _ground(self, monkeypatch, request, unknowns):
        import autornd.knowledge.context as ctx
        from autornd.models.verdicts import Domain, RiskLevel

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
        monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        monkeypatch.setattr(research, "MAX_ROUNDS", 1)
        client = _client(_reply(quotes=[(1, PASSAGE, PAGE)]))
        client.chat_json = AsyncMock(return_value=({
            "objective": "o", "unknowns": unknowns,
            "blocking_unknowns": unknowns,
            "assumptions": [], "considerations": []}, None))
        record: dict = {}
        await ctx.build_phase_context(
            request, [Domain.HARDWARE], client=client,
            risk=RiskLevel.LOW, grounding_lookup=record)
        return client, record

    async def test_a_low_risk_request_that_asks_to_be_cited_is_looked_up(
            self, monkeypatch):
        client, record = await self._ground(
            monkeypatch, "What is the limit? Cite the datasheet.", ["the limit"])
        assert client.chat.await_count == 1
        assert record["asked"] == ["the limit"]
        assert record["sources"][0]["quotes"][0]["status"] == "found"

    async def test_a_low_risk_request_that_asks_for_nothing_is_not(self, monkeypatch):
        """Break-proof: the risk gate still declines when no source is asked for."""
        client, record = await self._ground(
            monkeypatch, "What is the limit?", ["the limit"])
        assert client.chat.await_count == 0 and record == {}

    async def test_with_no_gap_found_the_request_itself_is_the_question(
            self, monkeypatch):
        request = "What is the limit? Give it with sources."
        client, record = await self._ground(monkeypatch, request, [])
        assert client.chat.await_count == 1
        assert record["asked"] == [request]

    @pytest.mark.parametrize("request_text, demanded", [
        ("Cite the datasheet.", True),
        ("Give the limit, with sources.", True),
        ("Quote the rule.", True),
        ("Size the resistor for 20 mA.", False),
        ("The design references the existing schema.", False),
    ])
    def test_what_counts_as_asking(self, request_text, demanded):
        from autornd.knowledge.context import request_demands_sources
        assert request_demands_sources(request_text) is demanded


class TestAnXmlPageIsRead:
    async def test_xml_is_read_with_its_markup_dropped(self, monkeypatch):
        """govinfo.gov serves the CFR as XML; on 2026-11-12 both such pages a
        lookup quoted were recorded unfetched for their content type."""
        body = f"<?xml version='1.0'?><SECTION><P>{PASSAGE}</P></SECTION>".encode()
        monkeypatch.setattr(fetch, "_transport", _served({
            PAGE: (200, {"content-type": "application/xml"}, body)}))
        finding, = await research_gaps(
            _client(_reply(quotes=[(1, PASSAGE, PAGE)])), "a radio", ["The EU 868 MHz limit"])
        assert finding.quotes[0].status == "found"


def _zip(members: dict[str, str]) -> bytes:
    import io
    import zipfile
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return out.getvalue()


def _epub(*chapters: str) -> bytes:
    """A book whose spine lists its chapters in the order given, which is
    the reverse of their file names."""
    names = [f"c{len(chapters) - i}.xhtml" for i in range(len(chapters))]
    manifest = "".join(f'<item id="i{i}" href="{n}"/>' for i, n in enumerate(names))
    spine = "".join(f'<itemref idref="i{i}"/>' for i in range(len(names)))
    return _zip({
        "mimetype": "application/epub+zip",
        "META-INF/container.xml": (
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>'),
        "OEBPS/book.opf": (
            '<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
            f"{manifest}</manifest><spine>{spine}</spine></package>"),
        **{f"OEBPS/{n}": f"<html><body><p>{c}</p><script>no</script></body></html>"
           for n, c in zip(names, chapters)},
    })


def _docx(*paragraphs: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    return _zip({"word/document.xml": f"<w:document><w:body>{body}</w:body></w:document>"})


def _pptx(*slides: str) -> bytes:
    return _zip({"ppt/presentation.xml": "<p:presentation/>", **{
        f"ppt/slides/slide{i}.xml": f"<p:sld><a:p><a:r><a:t>{s}</a:t></a:r></a:p></p:sld>"
        for i, s in enumerate(slides, 1)}})


def _xlsx(shared: str, number: str) -> bytes:
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    return _zip({
        "xl/workbook.xml": f"<workbook {ns}/>",
        "xl/sharedStrings.xml": f"<sst {ns}><si><t>{shared}</t></si></sst>",
        "xl/worksheets/sheet1.xml": (
            f'<worksheet {ns}><sheetData><row><c t="s"><v>0</v></c>'
            f"<c><v>{number}</v></c></row></sheetData></worksheet>"),
    })


def _encrypted(pdf: bytes, user_password: str) -> bytes:
    import io
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf)))
    writer.encrypt(user_password, owner_password="owner", algorithm="AES-256")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


OFFICE = "application/vnd.openxmlformats-officedocument."


class TestBooksDocumentsAndData:
    """What the fetch reads beyond pages and plain PDFs (owner, 2026-11-13)."""

    async def _read(self, monkeypatch, content_type: str, body: bytes):
        monkeypatch.setattr(fetch, "_transport", _served({
            PAGE: (200, {"content-type": content_type}, body)}))
        return await fetch.fetch_source(PAGE)

    async def test_a_pdf_encrypted_with_no_password_is_opened(self, monkeypatch):
        """Live 2026-11-13: a datasheet encrypted against editing was
        recorded failed with DependencyError."""
        body = _encrypted(_pdf(PASSAGE)[2], "")
        source = await self._read(monkeypatch, "application/pdf", body)
        assert source.status == "fetched" and PASSAGE in source.text

    async def test_a_pdf_that_needs_a_password_says_so(self, monkeypatch):
        body = _encrypted(_pdf(PASSAGE)[2], "secret")
        source = await self._read(monkeypatch, "application/pdf", body)
        assert source.status == "failed"
        assert source.reason == "the PDF could not be read: PasswordProtected"

    async def test_an_epub_is_read_in_its_reading_order(self, monkeypatch):
        source = await self._read(monkeypatch, "application/epub+zip",
                                  _epub("First chapter.", PASSAGE))
        assert source.status == "fetched"
        assert source.text.index("First chapter.") < source.text.index(PASSAGE)
        assert "no" not in source.text.split()

    async def test_an_epub_with_no_usable_package_file_is_still_read(self, monkeypatch):
        body = _zip({"mimetype": "application/epub+zip",
                     "a.xhtml": f"<html><body><p>{PASSAGE}</p></body></html>"})
        source = await self._read(monkeypatch, "application/epub+zip", body)
        assert source.status == "fetched" and PASSAGE in source.text

    @pytest.mark.parametrize("content_type, body, lines", [
        (OFFICE + "wordprocessingml.document", _docx("Scope.", PASSAGE),
         ["Scope.", PASSAGE]),
        (OFFICE + "presentationml.presentation", _pptx("Title", PASSAGE),
         ["Title", PASSAGE]),
        (OFFICE + "spreadsheetml.sheet", _xlsx("Limit, mW", "25"),
         ["Limit, mW\t25"]),
    ])
    async def test_an_office_document_is_read_line_by_line(
            self, monkeypatch, content_type, body, lines):
        source = await self._read(monkeypatch, content_type, body)
        assert source.status == "fetched"
        assert [l for l in source.text.splitlines() if l.strip()] == lines

    @pytest.mark.parametrize("content_type", [
        "application/json", "application/vnd.api+json"])
    async def test_json_is_read_as_its_keys_and_values(self, monkeypatch, content_type):
        """A database's answer: a quoted value is found as written, not
        behind JSON's escapes."""
        quoted = 'The limit is "25 mW" at 868 MHz (±1 %)'
        body = json.dumps({"record": {"title": quoted, "year": 2024,
                                      "tags": ["srd", None]}}).encode()
        source = await self._read(monkeypatch, content_type, body)
        assert source.status == "fetched"
        assert source.text.splitlines() == [
            f"title: {quoted}", "year: 2024", "tags: srd"]

    async def test_text_that_is_not_json_is_kept_as_it_came(self, monkeypatch):
        source = await self._read(monkeypatch, "application/json", b"{not json")
        assert source.status == "fetched" and source.text == "{not json"

    @pytest.mark.parametrize("body, found", [
        (_pdf(PASSAGE)[2], True),
        (_epub(PASSAGE), True),
        (_docx(PASSAGE), True),
        (_zip({"readme.txt": PASSAGE}), False),
        (b"\x89PNG\r\n" + PASSAGE.encode(), False),
    ])
    async def test_a_file_the_server_did_not_name_is_read_by_what_it_is(
            self, monkeypatch, body, found):
        source = await self._read(monkeypatch, "application/octet-stream", body)
        if found:
            assert source.status == "fetched" and PASSAGE in source.text
        else:
            assert source.status == "failed" and source.reason == (
                "content type application/octet-stream is not read as text")

    async def test_a_zip_that_unpacks_too_large_is_not_read(self, monkeypatch):
        monkeypatch.setattr(fetch, "ZIP_MAX_BYTES", 1000)
        source = await self._read(monkeypatch, OFFICE + "wordprocessingml.document",
                                  _docx("x" * 2000))
        assert source.status == "failed"
        assert source.reason == "the document could not be read: UnpacksTooLarge"

    async def test_a_document_with_no_text_says_so(self, monkeypatch):
        source = await self._read(monkeypatch, OFFICE + "wordprocessingml.document",
                                  _docx())
        assert source.status == "failed"
        assert source.reason == "the document has no text"
