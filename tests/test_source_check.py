"""Ruling D56: a finding is checked against its source.

The lookup asks the search model where the answer is written. The harness
fetches each page named, records which version it read, and hands on the
page's own words; each passage handed on is looked for in its page. Only a
found passage is kept for later runs. The lookup that asked the search model
for an answer and its quotes, and its second round, were removed on
2026-11-16 with their tests.

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
    MIN_QUOTE_CHARS, RESEARCH_TAG, Finding, Quote, quote_found,
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
    research.reset_unreadable_sites()
    yield
    research.reset_unreadable_sites()


def _documents(*items) -> ModelResponse:
    content = json.dumps({"documents": [
        {"url": url, "title": "t", "near": near} for url, near in items]})
    return ModelResponse(content=content, model="search/model", prompt_tokens=10,
                         completion_tokens=20, cost=0.005, citations=[])


def _client(*replies: ModelResponse):
    client = AsyncMock()
    client.chat = AsyncMock(side_effect=list(replies))
    return client


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

    async def test_pages_fetched_per_lookup_are_bounded(self, monkeypatch):
        seen: list[str] = []
        pages = {f"{PAGE}/{n}": _text(PASSAGE)
                 for n in range(research.MAX_DOCUMENTS + 1)}
        monkeypatch.setattr(fetch, "_transport", _served(pages, seen))
        finding, = await research_gaps(
            _client(_documents(*[(url, "") for url in pages])),
            "a radio", ["The EU 868 MHz limit"])
        assert len(seen) == research.MAX_DOCUMENTS == len(finding.documents)


class TestOnlyAFoundPassageIsKept:
    async def test_each_found_passage_is_stored_under_its_own_page(self, monkeypatch):
        stored: list[tuple[str, str, str]] = []
        monkeypatch.setattr(research, "ingest_text",
                            lambda text, tag, source="": stored.append((text, tag, source)))
        monkeypatch.setattr(fetch, "_transport", _served(
            {PAGE: _html(), OTHER: _text(CELL), REFUSING: REFUSED}))
        await research_gaps(
            _client(_documents((PAGE, ""), (OTHER, ""), (REFUSING, ""))),
            "a radio", ["The LiFePO4 cutoff"])
        # The page that could not be read is not kept.
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
        await research_gaps(_client(_documents((PAGE, ""))), "a radio",
                            ["The EU 868 MHz limit"])
        assert seen["where"] == {"tag": "research-quoted"}

    @pytest.mark.parametrize("distance, reused", [(0.1, True), (0.2, False)])
    async def test_only_a_near_restatement_is_reused(self, monkeypatch, distance, reused):
        """Cosine distance: the old 0.35 squared-L2 intent is 0.175 here."""
        monkeypatch.setattr(research, "retrieve", lambda *a, **k: [{
            "text": f'Q: The EU 868 MHz limit\nThe page says: "{PASSAGE}"',
            "source": PAGE, "tag": RESEARCH_TAG, "distance": distance}])
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        client = _client(_documents((PAGE, "")))
        findings = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert (client.chat.await_count == 0) is reused
        assert (findings[0].model == "recalled") is reused

    async def test_a_recalled_passage_is_not_looked_up_or_marked(self, monkeypatch):
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
        monkeypatch.setattr(fetch, "_transport",
                            _served({PAGE: _html(), REFUSING: REFUSED}))
        client = _client(_documents((PAGE, ""), (REFUSING, "")))
        client.chat_json = AsyncMock(return_value=({
            "objective": "size it", "unknowns": ["the limit", "the duty cycle"],
            "blocking_unknowns": ["the limit", "the duty cycle"],
            "assumptions": [], "considerations": []}, None))
        record: dict = {}
        out = await ctx.build_phase_context(
            "size a radio", [Domain.HARDWARE], client=client,
            risk=RiskLevel.HIGH, grounding_lookup=record)
        assert record["quotes"] == {"found": 1, "not_found": 0, "unfetched": 1,
                                    "too_short": 0}
        assert "asked_again" not in record and record["found"] == 1
        assert "have answers no passage found in its page backs" not in out
        assert PASSAGE[:40] in out


def test_a_finding_built_the_old_way_is_one_unverified_question():
    finding = Finding("q", "a", ["https://x/y"])
    assert finding.unchecked() == [1]
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


# The page's words as fetched from ecfr.gov on 2026-11-14 (40 CFR 141.62(b)),
# and the quotes are the search model's own, from the lookup test's trace.
TABLE_PAGE = ("non-transient, non-community water systems. Contaminant MCL (mg/l) "
              "(1) Fluoride 4.0 (2) Asbestos 7 Million Fibers/liter (longer than "
              "10 \u03bcm) (3) Barium 2 (4) Cadmium 0.005 (5) Chromium 0.1 "
              "(6) Mercury 0.002 (7) Nitrate 10 (as Nitrogen) (8) Nitrite 1 (as "
              "Nitrogen) (16) Arsenic 0.010")


class TestAQuotedTableIsReadRowByRow:
    @pytest.mark.parametrize("quote", [
        "|(7) Nitrate|10 (as Nitrogen)|",
        "|Contaminant|MCL (mg/l)|\n|--|--|\n|(1) Fluoride|4.0|\n"
        "|(7) Nitrate|10 (as Nitrogen)|\n|(16) Arsenic|0.010|",
        "| Contaminant | MCL (mg/l) |\n|:--|--:|\n| (2) Asbestos | 7 Million "
        "Fibers/liter (longer than 10 \u00b5m) |",
    ])
    def test_a_grid_of_cells_is_found_when_each_row_is_on_the_page(self, quote):
        """Measured 2026-11-15: 11 such quotes held the answer, none found."""
        assert quote_found(quote, TABLE_PAGE)

    @pytest.mark.parametrize("quote", [
        # A changed figure in one cell.
        "|Contaminant|MCL (mg/l)|\n|--|--|\n|(7) Nitrate|100 (as Nitrogen)|",
        # A figure put beside another row's name.
        "|Contaminant|MCL (mg/l)|\n|--|--|\n|(3) Barium|0.005|",
        # Rows the page prints in the other order.
        "|(7) Nitrate|10 (as Nitrogen)|\n|(1) Fluoride|4.0|",
    ])
    def test_a_changed_cell_or_a_row_out_of_place_is_not_found(self, quote):
        """Break-proof: the rows are matched whole, cells side by side."""
        assert not quote_found(quote, TABLE_PAGE)

    def test_a_grid_too_short_to_check_is_not_found(self):
        assert not quote_found("|(3) Barium|2|", TABLE_PAGE)

    def test_prose_with_a_bar_in_it_is_still_read_as_prose(self):
        """A quote is a grid only when every line of it is."""
        assert not quote_found("(7) Nitrate | 10 (as Nitrogen)", TABLE_PAGE)
        assert quote_found("(7) Nitrate 10 (as Nitrogen)", TABLE_PAGE)


# A page's words as eCFR prints them (29 CFR 1910.95(g)(5)), and quotes in
# the forms the search model wrote them in the lookup tests of 2026-11-14.
NOISE_PAGE = ("\u00a7 1910.95 Occupational noise exposure. (g) Audiometric testing "
              "program. (5) Baseline audiogram. (i) Within 6 months of an "
              "employee's first exposure at or above the action level, the "
              "employer shall establish a valid baseline audiogram against which "
              "subsequent audiograms can be compared. (ii) Mobile test van "
              "exception. (iii) Testing to establish a baseline audiogram shall "
              "be preceded by at least 14 hours without exposure to workplace "
              "noise.")


class TestAModelsOwnMarksAreNotWordsOfThePassage:
    @pytest.mark.parametrize("quote", [
        # Emphasis stars the page does not print.
        "(5) *Baseline audiogram.* (i) Within 6 months of an employee's "
        "first exposure at or above the action level",
        "(g) **Audiometric testing program.** (5) *Baseline audiogram.*",
        # The hashes of a heading.
        "#### \u00a7 1910.95 Occupational noise exposure.\n(g) Audiometric "
        "testing program.",
    ])
    def test_stars_and_heading_hashes_change_no_word(self, quote):
        """Measured 2026-11-14: 12 recorded quotes were on their pages word
        for word and were marked not found for these marks."""
        assert quote_found(quote, NOISE_PAGE)

    @pytest.mark.parametrize("quote", [
        # A changed figure under the marks.
        "(iii) *Testing* to establish a baseline audiogram shall be preceded "
        "by at least 24 hours",
        # A row of dots where words were left out: still not allowed (D56).
        "(i) Within 6 months of an employee's first exposure at or above the "
        "action level\n...\n(iii) Testing to establish a baseline audiogram",
        # A heading, then a paragraph that does not follow it on the page.
        "#### \u00a7 1910.95 Occupational noise exposure.\n(i) Within 6 months "
        "of an employee's first exposure at or above the action level",
    ])
    def test_a_changed_word_or_words_left_out_are_still_not_found(self, quote):
        """Break-proof: the marks are dropped, the words are not."""
        assert not quote_found(quote, NOISE_PAGE)

    @pytest.mark.parametrize("quote, page", [
        # The tildes of a subscript.
        ("The level of the standard for ozone (O~3~) is 0.070 parts per million",
         "The level of the standard for ozone (O3) is 0.070 parts per million (ppm)."),
        # The carets of a superscript (the harder professional run: one
        # question lost its passage 3 runs of 3).
        ("an 8-hour TWA of 50 µg/m^3^ of respirable crystalline silica",
         "in excess of an 8-hour TWA of 50 µg/m3 of respirable crystalline silica."),
        # A list mark at the start, with or without a backslash.
        ("1. Verifiers SHALL require passwords to be a minimum of 15 characters.",
         "Password Verifiers Verifiers SHALL require passwords to be a minimum of "
         "15 characters."),
        ("1\\. Verifiers SHALL require passwords to be a minimum of 15 characters.",
         "Password Verifiers Verifiers SHALL require passwords to be a minimum of "
         "15 characters."),
        ("- Verifiers SHALL require passwords to be a minimum of 15 characters.",
         "Verifiers SHALL require passwords to be a minimum of 15 characters."),
    ])
    def test_a_subscript_mark_and_a_list_mark_change_no_word(self, quote, page):
        """Owner's ruling 2026-11-15, off the baseline's unmatched quotes."""
        assert quote_found(quote, page)

    def test_a_list_mark_does_not_hide_a_changed_figure(self):
        """Break-proof: the mark goes, the words stay compared."""
        assert not quote_found(
            "1. Verifiers SHALL require passwords to be a minimum of 15 characters.",
            "Verifiers SHALL require passwords to be a minimum of 8 characters.")

    def test_the_record_keeps_a_long_passage_whole(self):
        """Measured 2026-11-15: the lookup that reads the documents hands on
        excerpts of up to 1,200 characters, the record kept 600, and a
        figure past them could not be checked against the text handed on."""
        long, short = "a" * 599 + " " + "b" * 600, "c" * 600
        record, = research.source_records([research.Finding(
            question="q", answer="a",
            quotes=[research.Quote(1, long, "u"),
                                  research.Quote(1, short, "u")])])
        first, second = record["quotes"]
        assert (first["text"], first["whole"]) == (long[:600], long)
        assert second["text"] == short and "whole" not in second

    def test_marks_alone_are_too_short_to_check(self):
        assert not quote_found("*(5)* **(ii)**", NOISE_PAGE)

    def test_a_star_the_page_itself_prints_still_matches(self):
        assert quote_found("the limit is 25 mW* in this band at all times",
                           "Note: the limit is 25 mW* in this band at all times.")


REFUSING = "https://www.refusing.example.gov/rule/868"
REFUSED = (403, {"content-type": "text/html"}, b"Forbidden")


class TestASiteThatRefusesIsAvoided:
    """Owner's direction of 2026-11-14. Measured the same day: 116 of 409
    quotes were on one site that answers every fetch "HTTP 403"."""

    async def _refused(self, monkeypatch, times=2):
        monkeypatch.setattr(fetch, "_transport",
                            _served({REFUSING: REFUSED, PAGE: _html()}))
        for _ in range(times):
            await research_gaps(_client(_documents((REFUSING, PASSAGE))),
                                "a radio", ["The EU 868 MHz limit"])

    async def test_a_site_that_refuses_twice_is_listed(self, monkeypatch):
        await self._refused(monkeypatch)
        assert research.unreadable_sites() == {"refusing.example.gov": "HTTP 403"}

    async def test_one_refusal_lists_nothing(self, monkeypatch):
        """Break-proof. Measured 2026-11-14: one challenge page listed
        ecfr.gov, and 3 of 8 answers told to avoid it were wrong."""
        await self._refused(monkeypatch, times=1)
        assert research.unreadable_sites() == {}

    async def test_a_site_read_here_is_never_listed(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({REFUSING: _html()}))
        await research_gaps(_client(_documents((REFUSING, PASSAGE))),
                            "a radio", ["The EU 868 MHz limit"])
        await self._refused(monkeypatch, times=3)
        assert research.unreadable_sites() == {}

    async def test_a_missing_page_says_nothing_about_its_site(self, monkeypatch):
        """Break-proof: only a refusal marks a site, not any failed fetch."""
        await research_gaps(_client(_documents((OTHER, PASSAGE))),
                            "a radio", ["The EU 868 MHz limit"])
        assert research.unreadable_sites() == {}

    async def test_a_page_read_from_the_site_takes_it_off_the_list(self, monkeypatch):
        """A listed site is not fetched while the switch is on, so this is
        seen with it off: the list is kept either way."""
        monkeypatch.setattr(config.settings, "lookup_avoid_unreadable", False)
        await self._refused(monkeypatch)
        assert research.unreadable_sites() != {}
        monkeypatch.setattr(fetch, "_transport", _served({REFUSING: _html()}))
        await research_gaps(_client(_documents((REFUSING, PASSAGE))),
                            "a radio", ["The EU 868 MHz limit"])
        assert research.unreadable_sites() == {}

    async def test_the_next_lookup_is_told_to_give_no_address_there(self, monkeypatch):
        assert config.settings.lookup_avoid_unreadable is True, "on since 2026-11-15"
        await self._refused(monkeypatch, times=1)
        client = _client(_documents((REFUSING, PASSAGE)), _documents((PAGE, "")))
        await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        finding, = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        asked_first, asked_next = (c.kwargs["user_message"]
                                   for c in client.chat.await_args_list)
        assert "refuse to be read" not in asked_first
        assert ("refuse to be read from here: refusing.example.gov. Give no "
                "address on them." in asked_next)
        assert finding.checked() == {1}

    async def test_switched_off_no_lookup_is_told_anything(self, monkeypatch):
        """Break-proof: the clause is the switch's."""
        monkeypatch.setattr(config.settings, "lookup_avoid_unreadable", False)
        await self._refused(monkeypatch, times=2)
        client = _client(_documents((PAGE, "")))
        await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert research.unreadable_sites() == {"refusing.example.gov": "HTTP 403"}
        assert all("refuse to be read" not in c.kwargs["user_message"]
                   for c in client.chat.await_args_list)


LONG_PAGE = "\n".join(
    [f"({n}) General provision number {n} about records and notices kept by "
     f"the certificate holder under this part." for n in range(1, 60)]
    + ["(c) Rest. A flight attendant scheduled to a duty period of 14 hours or "
       "less must be given a scheduled rest period of at least 10 consecutive "
       "hours."]
    + [f"({n}) Further provision number {n} about training and manuals."
       for n in range(60, 120)])


class TestTheLookupReadsTheDocuments:
    """Measured 2026-11-15 (the root-cause test): with the governing section's
    own text handed on, 8 of 8 answers were right on two questions that had
    been wrong 8 times on a search model's summary."""

    async def test_the_search_is_asked_where_not_what(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        client = _client(_documents((PAGE, "")))
        await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        asked = client.chat.await_args.kwargs["user_message"]
        assert "Do\nnot answer the request." in asked
        assert "Request:\na radio" in asked and "The EU 868 MHz limit" in asked
        assert client.chat.await_count == 1

    async def test_the_finding_carries_the_pages_own_words(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html()}))
        finding, = await research_gaps(
            _client(_documents((PAGE, ""))), "a radio", ["The EU 868 MHz limit"])
        quote, = finding.quotes
        assert quote.status == "found" and quote_found(PASSAGE, quote.text)
        assert quote.url == PAGE and quote.sha256
        assert "No summary was made." in finding.answer
        assert quote.text in finding.render() and finding.unchecked() == []

    async def test_a_long_page_gives_the_stretch_the_request_points_at(
            self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _text(LONG_PAGE)}))
        finding, = await research_gaps(
            _client(_documents((PAGE, ""))),
            "how much rest must a flight attendant get", ["rest period hours"])
        assert len(LONG_PAGE) > research.DOCUMENT_WHOLE_CHARS
        assert any("at least 10 consecutive hours" in q.text for q in finding.quotes)
        assert all(q.status == "found" for q in finding.quotes)
        assert sum(len(q.text) for q in finding.quotes) < len(LONG_PAGE) / 2

    async def test_the_search_models_pointer_finds_what_the_request_cannot(
            self, monkeypatch):
        """Break-proof for the chooser: a misspelt request shares no word
        with the passage, and the pointer's words still find it."""
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _text(LONG_PAGE)}))
        finding, = await research_gaps(
            _client(_documents((PAGE, "at least 10 consecutive hours"))),
            "flite attendnt brake", ["zzz"])
        assert any("at least 10 consecutive hours" in q.text for q in finding.quotes)

    async def test_a_page_not_read_is_recorded_and_the_search_is_asked_once(
            self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport",
                            _served({REFUSING: REFUSED, PAGE: _html()}))
        client = _client(_documents((REFUSING, "x"), (PAGE, "")))
        finding, = await research_gaps(client, "a radio", ["The EU 868 MHz limit"])
        assert [q.status for q in finding.quotes] == ["unfetched", "found"]
        assert finding.quotes[0].reason == "HTTP 403"
        assert client.chat.await_count == 1

    async def test_a_site_listed_as_refusing_is_not_fetched(self, monkeypatch):
        seen: list[str] = []
        monkeypatch.setattr(fetch, "_transport",
                            _served({REFUSING: REFUSED, PAGE: _html()}, seen))
        for _ in range(2):
            await research_gaps(_client(_documents((REFUSING, "x"))),
                                "a radio", ["The EU 868 MHz limit"])
        seen.clear()
        await research_gaps(_client(_documents((REFUSING, "x"), (PAGE, ""))),
                            "a radio", ["The EU 868 MHz limit"])
        assert seen == [PAGE]

    def test_it_is_the_only_lookup(self):
        """Owner's word 2026-11-16, after 432 answers read blind: 144 of 144
        right with it against 141 of 144. The lookup that asked for an
        answer, the second request for documents and the withholding of
        unverified answers are gone, and so are their settings."""
        for gone in ("lookup_reads_documents", "lookup_documents_ask_again",
                     "lookup_withhold_unverified"):
            assert gone not in config.Settings.model_fields
        assert not hasattr(research, "_ask") and not hasattr(research, "_lookup")


class TestWhatTheFetchCanRead:
    async def test_a_pdf_is_read_through_its_text_layer(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _pdf(PASSAGE)}))
        finding, = await research_gaps(
            _client(_documents((PAGE, PASSAGE))), "a radio", ["The EU 868 MHz limit"])
        assert finding.quotes[0].status == "found"
        assert quote_found(PASSAGE, finding.quotes[0].text)

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
        finding, = await research_gaps(
            _client(_documents((PAGE, PASSAGE))), "a radio", ["The EU 868 MHz limit"])
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


class TestAPageThatIsAFrameIsNotAPage:
    """Measured 2026-11-24 over the stored runs: legislation.gov.au and NVD addresses came back as a
    script's frame of 72 to 2,081 characters, were recorded as fetched, and a word search of them
    was reported as proof that the document does not state a figure. The document was never read."""

    FRAME = ("<html><head><title>Instrument - Federal Register</title></head><body>"
             "<app-root></app-root><noscript>Please enable JavaScript.</noscript></body></html>")
    API = ("https://api.prod.legislation.gov.au/v1/documents/find(titleId='F2015L01438',"
           "asAtSpecification='{v}',type='Primary',format='Pdf',uniqueTypeNumber=0,"
           "volumeNumber=0,rectificationVersionNumber=0)")

    @pytest.mark.parametrize("reader, version", [
        ("https://www.legislation.gov.au/F2015L01438", "latest"),
        ("https://www.legislation.gov.au/F2015L01438/latest/text", "latest"),
        ("https://legislation.gov.au/F2015L01438/latest", "latest"),
        ("https://www.legislation.gov.au/F2015L01438/asmade/text", "asmade"),
        ("https://www.legislation.gov.au/f2015l01438/ASMADE", "asmade"),
    ])
    def test_an_instrument_is_read_through_the_registers_document_route(self, reader, version):
        assert fetch.readable_address(reader) == self.API.format(v=version)

    @pytest.mark.parametrize("url", [
        "https://www.legislation.gov.au/F2015L01438/2023-03-02/text",   # a dated compilation
        "https://www.legislation.gov.au/",
        "https://www.legislation.gov.au/search?q=F2015L01438",
        "https://example.org/F2015L01438/latest",
    ])
    def test_a_form_the_route_does_not_cover_is_left_alone(self, url):
        assert fetch.readable_address(url) == url

    def test_a_cve_record_is_read_through_the_nvd_api(self):
        api = "https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2021-44228"
        for url in ("https://nvd.nist.gov/vuln/detail/CVE-2021-44228",
                    "https://nvd.nist.gov/vuln/detail/cve-2021-44228?ci%3D2558",
                    "https://nvd.nist.gov/vuln/detail/CVE-2021-44228#vulnCurrentDescriptionTitle"):
            assert fetch.readable_address(url) == api
        assert fetch.readable_address("https://nvd.nist.gov/vuln/search") == (
            "https://nvd.nist.gov/vuln/search")

    async def test_an_instrument_is_read_from_its_pdf(self, monkeypatch):
        reader = "https://www.legislation.gov.au/F2015L01438/latest/text"
        api = self.API.format(v="latest")
        seen: list[str] = []
        text = "The maximum field strength is 5 mW at 868 MHz. " * 8
        monkeypatch.setattr(fetch, "_transport", _served({api: _pdf(text)}, seen))
        source = await fetch.fetch_source(reader)
        assert source.status == "fetched" and seen == [api]
        assert "5 mW at 868 MHz" in source.text and source.url == reader

    async def test_a_frame_the_script_fills_is_not_read(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(self.FRAME)}))
        source = await fetch.fetch_source(PAGE)
        assert source.status == "failed" and not source.fetched and source.text == ""
        assert "shell" in source.reason

    async def test_a_page_the_script_has_filled_is_a_page(self, monkeypatch):
        full = self.FRAME.replace("<app-root></app-root>",
                                  "<app-root><p>" + "The limit is stated here. " * 200
                                  + "</p></app-root>")
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(full)}))
        source = await fetch.fetch_source(PAGE)
        assert source.fetched and fetch.SHELL_MAX_CHARS < len(source.text)

    async def test_a_short_page_with_no_frame_is_a_page(self, monkeypatch):
        short = "<html><body><p>Charge each cell to 3.65 V.</p></body></html>"
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(short)}))
        assert (await fetch.fetch_source(PAGE)).fetched

    async def test_a_frame_is_recorded_as_unfetched_and_proves_nothing(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(self.FRAME)}))
        finding, = await research_gaps(
            _client(_documents((PAGE, PASSAGE))), "a radio", ["The EU 868 MHz limit"])
        quote, = finding.quotes
        assert quote.status == "unfetched" and "shell" in quote.reason


class TestADspaceFrameIsFollowedToItsFile:
    """X3 (2026-11-25): iris.who.int answered the address of a PDF with a 755-byte DSpace frame, it was recorded as fetched with 33
    characters, and the WHO air quality guidelines (a PDF of 7 MB behind the repository's API) were never read."""

    HOST = "https://repo.example.org"
    FRAME = ("<html><head><title>DSpace</title></head><body><ds-app></ds-app>"
             "<script src='main.js' type='module'></script></body></html>")
    TEXT = "SO2 24-hour interim targets 125 50 and the AQG level 40 micrograms per cubic metre. " * 4
    ITEM = HOST + "/server/api/core/items/5b0ca7ab-830a-44b8-b99f-4ee743b4d7b2"

    def _api(self, *, content="/server/api/core/bitstreams/b1/content", names=("guidelines.pdf",)):
        j = lambda body: (200, {"content-type": "application/hal+json"}, json.dumps(body).encode())  # noqa: E731
        streams = [{"name": n, "_links": {"content": {"href": self.HOST + content.replace("b1", f"b{i}")}}}
                   for i, n in enumerate(names, 1)]
        return {
            self.HOST + "/server/api/pid/find?id=hdl:10665/345329": (302, {"location": self.ITEM}, b""),
            self.ITEM: j({"_links": {"bundles": {"href": self.ITEM + "/bundles"}}}),
            self.ITEM + "/bundles": j({"_embedded": {"bundles": [
                {"name": "LICENSE", "_links": {"bitstreams": {"href": self.HOST + "/x"}}},
                {"name": "ORIGINAL", "_links": {"bitstreams": {"href": self.HOST + "/server/api/core/bundles/o/bitstreams"}}}]}}),
            self.HOST + "/server/api/core/bundles/o/bitstreams": j({"_embedded": {"bitstreams": streams}}),
            self.HOST + "/server/api/core/bitstreams/b1/content": _pdf(self.TEXT),
            self.HOST + "/server/api/core/bitstreams/b2/content": _pdf("The second file is another document. " * 8),
        }

    @pytest.mark.parametrize("address", [
        "/bitstream/handle/10665/345329/guidelines.pdf",
        "/bitstream/handle/10665/345329/guidelines.pdf?sequence=1&isAllowed=y",
        "/handle/10665/345329",
    ])
    async def test_a_frame_at_a_documents_address_is_read_from_the_repository(self, monkeypatch, address):
        pages = {self.HOST + address.split("?")[0]: _html(self.FRAME), **self._api()}
        if "?" in address:
            pages[self.HOST + address] = _html(self.FRAME)
        monkeypatch.setattr(fetch, "_transport", _served(pages))
        source = await fetch.fetch_source(self.HOST + address)
        assert source.fetched and "AQG level 40" in source.text
        assert source.url == self.HOST + address and source.final_url.endswith("/bitstreams/b1/content")

    async def test_the_file_named_in_the_address_is_the_one_read(self, monkeypatch):
        pages = {self.HOST + "/bitstream/handle/10665/345329/other.pdf": _html(self.FRAME),
                 **self._api(names=("guidelines.pdf", "other.pdf"))}
        monkeypatch.setattr(fetch, "_transport", _served(pages))
        source = await fetch.fetch_source(self.HOST + "/bitstream/handle/10665/345329/other.pdf")
        assert source.fetched and "second file" in source.text

    async def test_an_item_address_reads_the_item_without_a_handle_lookup(self, monkeypatch):
        seen: list[str] = []
        address = self.HOST + "/items/5b0ca7ab-830a-44b8-b99f-4ee743b4d7b2"
        monkeypatch.setattr(fetch, "_transport", _served({address: _html(self.FRAME), **self._api()}, seen))
        assert (await fetch.fetch_source(address)).fetched
        assert not any("pid/find" in u for u in seen)

    async def test_a_hop_that_fails_leaves_the_frame_unread(self, monkeypatch):
        api = self._api()
        del api[self.ITEM + "/bundles"]
        monkeypatch.setattr(fetch, "_transport",
                            _served({self.HOST + "/handle/10665/345329": _html(self.FRAME), **api}))
        source = await fetch.fetch_source(self.HOST + "/handle/10665/345329")
        assert source.status == "failed" and "shell" in source.reason

    async def test_a_file_on_another_host_is_not_followed(self, monkeypatch):
        api = self._api(content="/server/api/core/bitstreams/b1/content")
        api[self.HOST + "/server/api/core/bundles/o/bitstreams"] = (
            200, {"content-type": "application/hal+json"},
            json.dumps({"_embedded": {"bitstreams": [{"name": "g.pdf", "_links": {"content": {
                "href": "https://elsewhere.example.net/g.pdf"}}}]}}).encode())
        seen: list[str] = []
        monkeypatch.setattr(fetch, "_transport",
                            _served({self.HOST + "/handle/10665/345329": _html(self.FRAME), **api}, seen))
        assert (await fetch.fetch_source(self.HOST + "/handle/10665/345329")).status == "failed"
        assert not any("elsewhere" in u for u in seen)

    async def test_a_frame_that_is_not_dspace_is_not_sent_to_a_repository_api(self, monkeypatch):
        seen: list[str] = []
        angular = self.FRAME.replace("<ds-app></ds-app>", "<app-root></app-root>")
        monkeypatch.setattr(fetch, "_transport",
                            _served({self.HOST + "/handle/10665/345329": _html(angular)}, seen))
        source = await fetch.fetch_source(self.HOST + "/handle/10665/345329")
        assert source.status == "failed" and seen == [self.HOST + "/handle/10665/345329"]

    async def test_a_tiny_page_that_loads_a_script_is_a_frame_whatever_its_root_is_called(self, monkeypatch):
        tiny = "<html><body><my-viewer></my-viewer><script src='a.js'></script></body></html>"
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(tiny)}))
        assert (await fetch.fetch_source(PAGE)).status == "failed"

    async def test_a_short_page_that_is_mostly_its_own_words_is_a_page_though_it_loads_a_script(self, monkeypatch):
        short = "<html><body><p>Charge each cell to 3.65 V, no higher.</p><script>1</script></body></html>"
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(short)}))
        assert (await fetch.fetch_source(PAGE)).fetched

    async def test_a_tiny_page_with_no_script_and_a_long_page_with_one_are_pages(self, monkeypatch):
        plain = "<html><body><p>Charge to 3.65 V.</p></body></html>"
        long = "<html><body><p>" + "The limit is stated here. " * 20 + "</p><script src='a.js'></script></body></html>"
        monkeypatch.setattr(fetch, "_transport", _served({PAGE: _html(plain), PAGE + "2": _html(long)}))
        assert (await fetch.fetch_source(PAGE)).fetched
        assert (await fetch.fetch_source(PAGE + "2")).fetched


class TestTheSourcesAreReturned:
    async def test_a_lookup_record_names_each_page_and_what_was_found(self, monkeypatch):
        monkeypatch.setattr(fetch, "_transport",
                            _served({PAGE: _html(), REFUSING: REFUSED}))
        findings = await research_gaps(
            _client(_documents((PAGE, PASSAGE), (REFUSING, "x"))),
            "a radio", ["The EU 868 MHz limit"])
        record, = research.source_records(findings)
        assert record["recalled"] is False
        assert "round" not in record and "withheld" not in record
        assert record["citations"] == [PAGE, REFUSING]
        assert record["unverified_questions"] == []
        assert [(q["question"], q["url"], q["status"]) for q in record["quotes"]] == [
            (1, PAGE, "found"), (1, REFUSING, "unfetched")]
        found = record["quotes"][0]
        assert quote_found(PASSAGE, found["text"])
        assert found["sha256"] and found["fetched_at"]
        assert [q["question_text"] for q in record["quotes"]] == [
            "The EU 868 MHz limit"] * 2
        assert [(d["url"], d["read"], d["holds_pointer"], d["request"])
                for d in record["documents"]] == [
            (PAGE, True, True, 1), (REFUSING, False, None, 1)]
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
        client = _client(_documents((PAGE, "")))
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
        # The request is asked beside the gap scoping named (owner's ruling
        # of 2026-11-21), in the one lookup.
        assert record["asked"] == ["What is the limit? Cite the datasheet.",
                                   "the limit"]
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
            _client(_documents((PAGE, PASSAGE))), "a radio", ["The EU 868 MHz limit"])
        assert finding.quotes[0].status == "found"
        assert quote_found(PASSAGE, finding.quotes[0].text)


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
