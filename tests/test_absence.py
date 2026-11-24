"""Proofs of absence (owner's ruling of 2026-11-21, option C): knowledge/absence.py.

The question the owner ruled on: when the document states no figure, the run blocks on the ask (or invents
one), because a model cannot tell "I did not find it" from "it is not there". The ruling is that the harness
proves absence itself, by searching the full text of a page it read in full for the words the answer would be
printed with, and that only such a proof allows "none stated". These tests hold the search, the typed words
it is given, and the line a proof hands on.

The case that set it is X41 of the first hold-out set: the ATmega328P datasheet, whose key says that "a
search of its full text for 'junction', 'thermal resistance', 'dissipation' and degC/W finds none".
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from autornd.knowledge import absence
from autornd.knowledge.absence import (
    MAX_TERM_CHARS, MAX_TERMS, MIN_TERMS, Proof, Searchable, TermsVerdict, clean_terms,
    name_terms, prove, provable_asks, render_proofs,
)
from autornd.routing.openrouter import BudgetExceeded

# The words X41's key names, and the way a datasheet that states the figure would print them.
WORDS = ["thermal resistance", "junction-to-ambient", "θJA", "°C/W"]
DATASHEET = ("Absolute Maximum Ratings. Operating Temperature -55°C to +125°C. "
             "DC Current per I/O Pin 40.0 mA. DC Current VCC and GND Pins 200.0 mA. "
             # long enough to be a document: a page under MIN_PROOF_PAGE_CHARS (200) proves nothing
             "Supply Voltage 1.8V to 5.5V. Clock Frequency 0 to 20 MHz. Package options: 28-pin SOIC, 32-pin TQFP.")


def page(text, url="https://example.org/ds.pdf", pages=0):
    return SimpleNamespace(text=text, url=url, pages=pages, fetched_at="2026-11-21T08:00:00Z",
                           sha256="3f2a9c1d77be" + "0" * 52)


class TestTheSearchIgnoresWhatLayoutDoesToAWord:
    """A page's layout changes how a word is printed, never the word. A proof that a word is absent has
    to be as hard to satisfy as the print is varied, or it would call present words absent."""

    @pytest.mark.parametrize("text", [
        "Thermal Resistance, junction to ambient: 45",
        "THERMAL    RESISTANCE",
        "the thermal\nresistance of the package",
        "the thermal resis-\ntance of the package",
        "the thermal resis- tance of the package",
        "the thermal\u00adresistance of the package",
        "thermal-resistance",
        "thermal\u2013resistance",
    ])
    def test_a_long_word_is_found_however_the_page_breaks_or_spaces_it(self, text):
        assert Searchable(text).has("thermal resistance")

    @pytest.mark.parametrize("text", [
        "Junction-to-ambient", "junction to ambient", "Junction\u2013to\u2013Ambient",
        "JUNCTION - TO - AMBIENT",
    ])
    def test_hyphens_dashes_and_spaces_between_words_are_one_thing(self, text):
        assert Searchable(text).has("junction-to-ambient")

    def test_a_ligature_and_a_compatibility_form_are_found(self):
        assert Searchable("the \ufb01rst speci\ufb01cation").has("first specification")

    def test_a_compatibility_form_that_case_folding_does_not_reach_is_found(self):
        """Case folding turns a ligature into its letters, so the test above would pass without NFKC;
        it does not turn a full-width letter into its plain one, and NFKC does."""
        assert Searchable("ＴＨＥＲＭＡＬ ＲＥＳＩＳＴＡＮＣＥ").has("thermal resistance")

    @pytest.mark.parametrize("printed", ["θJA", "ΘJA", "\u03d1JA", "\u03f4JA"])
    def test_every_form_of_the_theta_symbol_is_one_letter(self, printed):
        assert Searchable(f"R{printed} = 45").has("θJA")

    @pytest.mark.parametrize("printed", ["°C/W", "\u00baC/W", "\u02daC/W", "\u1d52C/W", "\u2103/W", "°C / W", "°C/ W"])
    def test_the_degree_sign_and_its_lookalikes_are_one_thing(self, printed):
        """A datasheet prints the degree as a masculine ordinal as often as not, and NFKC alone would turn
        that into the letter o."""
        assert Searchable(f"Rth = 45 {printed}").has("°C/W")

    def test_an_empty_word_is_not_found_so_it_can_never_stop_or_make_a_proof(self):
        """Nothing is in every text, so an empty word that was found would veto every proof."""
        for word in ("", "   "):
            assert not Searchable(DATASHEET).has(word)

    def test_a_word_that_is_not_there_is_not_found(self):
        assert not Searchable(DATASHEET).has("thermal resistance")
        assert not Searchable(DATASHEET).has("junction")
        assert not Searchable(DATASHEET).has("°C/W")

    def test_a_short_word_is_found_inside_a_longer_one_which_can_only_stop_a_proof(self):
        """'rth' is in 'worth'. A short word is matched as written, so it is found there, and a proof
        needs every word absent: the cost of a short word is a proof that does not form, never one
        that forms wrongly."""
        assert Searchable("it is worth it").has("Rth")

    def test_a_short_symbol_is_not_found_in_unrelated_letters(self):
        """With the marks dropped '°C/W' would be 'cw', which is in a great many texts."""
        assert not Searchable("lacework, brickwork, a cwm").has("°C/W")

    @pytest.mark.parametrize("dash", ["\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"])
    def test_a_short_word_with_a_hyphen_is_found_whatever_dash_the_page_prints(self, dash):
        """A short word keeps its punctuation, so the hyphen in it has to be one character whatever dash a
        page prints; a long word loses its hyphen in the squash and would never show a missing one."""
        assert Searchable(f"Rθ{dash}JA = 45").has("θ-JA")

    @pytest.mark.parametrize("mark", ["\u00ad", "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"])
    def test_a_short_word_is_found_when_the_page_puts_an_invisible_mark_inside_it(self, mark):
        """A soft hyphen or a zero-width mark is no character of the word, and a short word keeps its
        punctuation, so the mark has to be taken out of the text and not only ignored by the squash."""
        assert Searchable(f"Rth = 45 °C{mark}/W").has("°C/W")


class TestCleaningTheWords:
    def test_what_is_not_a_list_is_no_words(self):
        """A tuple, a set and a dict can be walked, and would be read as words if the list check were
        missing; a string would only be read as letters, which are dropped, and would show nothing."""
        for raw in (None, "thermal resistance", {"a": 1}, 3, ("thermal resistance", "junction"),
                    {"thermal resistance": 1}, {"thermal resistance", "junction"}):
            assert clean_terms(raw) == []

    def test_a_null_is_none_listed_in_the_verdict_itself(self):
        assert TermsVerdict(terms=None).terms == []
        assert TermsVerdict(terms=[{"ask": 1, "any_of": None}]).terms[0].any_of == []

    def test_only_strings_are_kept_and_spaces_are_one_space(self):
        assert clean_terms([" thermal   resistance ", 4, None, ["x"], "θJA"]) == [
            "thermal resistance", "θJA"]

    def test_a_word_of_fewer_than_two_letters_or_digits_is_dropped(self):
        assert clean_terms(["R", "°", "/", "  ", "°C/W"]) == ["°C/W"]

    def test_a_sentence_is_not_a_word(self):
        long = "the thermal resistance from the junction to the ambient air of this package"
        assert len(long) > MAX_TERM_CHARS
        assert clean_terms([long, "θJA"]) == ["θJA"]

    def test_the_same_word_in_another_layout_is_kept_once_and_the_first_wins(self):
        assert clean_terms(["Thermal Resistance", "thermal-resistance", "thermal  resistance",
                            "THERMAL RESISTANCE"]) == ["Thermal Resistance"]

    def test_at_most_max_terms_are_kept_in_order(self):
        raw = [f"word number {i}" for i in range(MAX_TERMS + 5)]
        assert clean_terms(raw) == raw[:MAX_TERMS]


class TestTheProof:
    def test_a_page_with_none_of_the_words_is_a_proof_that_says_how_big_the_page_is(self):
        proofs = prove({1: WORDS}, {"https://example.org/ds.pdf": page(DATASHEET, pages=653)})
        assert proofs == [Proof(
            ask=1, terms=tuple(WORDS), url="https://example.org/ds.pdf", chars=len(DATASHEET),
            pages=653, fetched_at="2026-11-21T08:00:00Z", sha256="3f2a9c1d77be" + "0" * 52)]

    @pytest.mark.parametrize("word", WORDS)
    def test_any_one_word_on_the_page_means_no_proof(self, word):
        """All the words must be absent: a document that states the answer prints at least one of them."""
        text = DATASHEET + f" See {word}."
        assert prove({1: WORDS}, {"u": page(text)}) == []

    def test_a_word_split_across_a_line_break_still_means_no_proof(self):
        text = DATASHEET + " The thermal resis-\ntance is 45."
        assert prove({1: WORDS}, {"u": page(text)}) == []

    def test_an_empty_extraction_proves_nothing(self):
        """A PDF that extracted as 33 characters was read "in full" and proved both asks of X3 absent on
        2026-11-24; a page with no text finds no word, so it cannot be a search of a document."""
        from autornd.knowledge.absence import MIN_PROOF_PAGE_CHARS
        assert MIN_PROOF_PAGE_CHARS == 200
        assert prove({1: WORDS}, {"u": page("x" * 33)}) == []
        assert prove({1: WORDS}, {"u": page("x" * (MIN_PROOF_PAGE_CHARS - 1))}) == []
        assert len(prove({1: WORDS}, {"u": page("x" * MIN_PROOF_PAGE_CHARS)})) == 1

    def test_fewer_than_the_least_words_is_no_proof(self):
        assert MIN_TERMS == 3
        assert prove({1: WORDS[:MIN_TERMS - 1]}, {"u": page(DATASHEET)}) == []
        assert len(prove({1: WORDS[:MIN_TERMS]}, {"u": page(DATASHEET)})) == 1

    def test_each_ask_and_each_page_is_judged_alone(self):
        pages = {"a": page(DATASHEET + " thermal resistance 45", url="a"),
                 "b": page(DATASHEET, url="b")}
        proofs = prove({1: WORDS, 2: ["maximum power", "power dissipation", "total power"]}, pages)
        assert [(p.ask, p.url) for p in proofs] == [(1, "b"), (2, "a"), (2, "b")]

    def test_a_page_that_was_not_read_in_full_is_not_passed_and_proves_nothing(self):
        """`prove` is given the pages read in full. A page that timed out or was refused is not among
        them, so it cannot be a page 'with none of the words'."""
        assert prove({1: WORDS}, {}) == []

    def test_an_ask_with_no_words_is_no_proof(self):
        assert prove({1: []}, {"u": page(DATASHEET)}) == []
        assert prove({}, {"u": page(DATASHEET)}) == []

    def test_a_page_with_a_figure_for_another_ask_is_not_a_proof_for_this_one(self):
        text = DATASHEET + " Total power dissipation 1.5 W."
        proofs = prove({1: WORDS, 2: ["power dissipation", "total power", "maximum power"]},
                       {"u": page(text)})
        assert [p.ask for p in proofs] == [1]


class TestTheLineAProofHandsOn:
    def test_it_names_the_ask_the_words_the_page_its_size_and_its_hash(self):
        line = prove({2: WORDS}, {"https://example.org/ds.pdf": page(DATASHEET, pages=653)})[0].render()
        assert line.startswith("- Ask 2: none of ")
        for word in WORDS:
            assert f'"{word}"' in line
        assert "anywhere in the full text of https://example.org/ds.pdf" in line
        assert f"653 pages, {len(DATASHEET):,} characters" in line
        assert "fetched 2026-11-21T08:00:00Z" in line and "sha256 3f2a9c1d77be)" in line

    def test_a_page_without_a_page_count_says_only_its_characters(self):
        line = prove({1: WORDS}, {"u": page(DATASHEET)})[0].render()
        assert "pages" not in line and f"{len(DATASHEET):,} characters" in line

    def test_no_proof_is_no_line_and_no_heading(self):
        assert render_proofs([]) == []

    def test_the_heading_says_who_made_the_proof_and_that_it_is_about_one_page(self):
        lines = render_proofs(prove({1: WORDS}, {"u": page(DATASHEET)}))
        assert lines[0].startswith("Proofs of absence, made by the harness (not a model)")
        assert "Each is about the page it names and no other" in lines[0]
        assert len(lines) == 2

    def test_the_record_is_plain_data(self):
        record = prove({1: WORDS}, {"u": page(DATASHEET, pages=7)})[0].as_record()
        assert record == {"ask": 1, "terms": WORDS, "url": "u", "chars": len(DATASHEET), "pages": 7,
                          "fetched_at": "2026-11-21T08:00:00Z", "sha256": "3f2a9c1d77be" + "0" * 52}


ASKS = [
    {"number": 1, "quote": "the junction-to-ambient thermal resistance", "kind": "value"},
    {"number": 2, "quote": "the maximum power dissipation", "kind": "value"},
    {"number": 3, "quote": "list the steps in order", "kind": "step"},
    {"number": 4, "quote": "answer in a table", "kind": "format"},
    {"number": 5, "quote": "state whether the part is rated for it", "kind": "verdict"},
    {"number": 6, "quote": "stay under the stated limit", "kind": "constraint"},
]


class TestWhichAsksAreProvable:
    def test_a_figure_or_a_verdict_can_be_stated_by_a_document_and_a_step_or_a_form_cannot(self):
        assert provable_asks(ASKS) == {
            1: "the junction-to-ambient thermal resistance", 2: "the maximum power dissipation",
            5: "state whether the part is rated for it"}

    def test_the_whole_request_taken_as_the_one_ask_is_provable(self):
        """When nothing anchored, the whole request is the one ask and has no kind: every kind at once."""
        assert provable_asks([{"number": 1, "quote": "the whole request", "kind": ""}]) == {
            1: "the whole request"}

    def test_a_kind_is_read_as_the_asks_node_states_it(self):
        enum_like = SimpleNamespace(value="Value")
        assert provable_asks([SimpleNamespace(number=1, quote="q", kind=enum_like)]) == {1: "q"}

    def test_an_entry_without_a_number_or_a_quote_is_none(self):
        assert provable_asks([{"quote": "q", "kind": "value"}, {"number": 2, "quote": " ", "kind": "value"},
                              {"number": True, "quote": "q", "kind": "value"}]) == {}
        assert provable_asks(None) == {}


def double(reply=None, error=None):
    """A client whose chat_json gives `reply` (or raises `error`), recording what it was asked."""
    client = SimpleNamespace()
    calls: list[dict] = []

    async def chat_json(**kwargs):
        calls.append(kwargs)
        if error is not None:
            raise error
        return reply, SimpleNamespace(cost=0.0)

    client.chat_json = AsyncMock(side_effect=chat_json)
    return client, calls


@pytest.mark.asyncio
class TestNamingTheWords:
    async def test_only_the_asks_a_document_can_state_are_put_to_the_model_each_at_its_own_number(self):
        client, calls = double({"terms": []})
        await name_terms(client, "the whole request text", ASKS)
        (call,) = calls
        assert call["function"] == "triage" and call["schema"] is TermsVerdict
        message = call["user_message"]
        assert "the whole request text" in message
        assert "1. the junction-to-ambient thermal resistance" in message
        assert "2. the maximum power dissipation" in message
        assert "5. state whether the part is rated for it" in message
        for left_out in ("list the steps in order", "answer in a table", "stay under the stated limit"):
            assert left_out not in message

    async def test_the_call_is_made_with_thinking_off(self):
        """The cheapest tier is a reasoning model: at its default it spent all 2000 tokens thinking and
        returned no text on every request probed on 2026-11-23, so no proof was ever made. With thinking
        off the same requests came back in under 80 tokens. Medium effort and a bigger budget did not help."""
        client, calls = double({"terms": []})
        await name_terms(client, "r", ASKS)
        assert calls[0]["reasoning"] == {"enabled": False}

    async def test_no_provable_ask_is_no_call_and_no_cost(self):
        client, calls = double({"terms": []})
        assert await name_terms(client, "r", [ASKS[2], ASKS[3]]) == {}
        assert await name_terms(client, "r", None) == {}
        assert calls == []

    async def test_the_words_come_back_by_ask_cleaned_and_only_for_asks_that_were_put(self):
        client, _ = double({"terms": [
            {"ask": 1, "any_of": [" thermal   resistance", "θJA", 7, "R", "°C/W"]},
            {"ask": 2, "any_of": ["power dissipation"]},
            {"ask": 9, "any_of": ["an ask nobody put"]},
            {"ask": 3, "any_of": ["a step is not provable"]},
            {"ask": 1, "any_of": ["a second entry for ask 1 is ignored"]},
        ]})
        assert await name_terms(client, "r", ASKS) == {
            1: ["thermal resistance", "θJA", "°C/W"], 2: ["power dissipation"]}

    async def test_a_reply_of_the_wrong_shape_is_no_words(self):
        for reply in ({"terms": "none"}, {"words": []}, {"terms": [{"ask": "x", "any_of": []}]}):
            client, _ = double(reply)
            assert await name_terms(client, "r", ASKS) == {}

    async def test_a_null_list_is_none_listed(self):
        client, _ = double({"terms": [{"ask": 1, "any_of": None}]})
        assert await name_terms(client, "r", ASKS) == {1: []}

    async def test_a_failed_call_is_no_words_and_so_no_proof_never_a_failed_lookup(self):
        client, _ = double(error=RuntimeError("the provider refused"))
        assert await name_terms(client, "r", ASKS) == {}

    async def test_a_spend_refusal_is_the_runs_and_goes_up(self):
        client, _ = double(error=BudgetExceeded("over the ceiling"))
        with pytest.raises(BudgetExceeded):
            await name_terms(client, "r", ASKS)


class TestTheSourceNamesNoModelAndNoPrice:
    def test_no_model_id_or_price_is_written_in_the_module(self):
        """Hard rule 4: rates come from the provider's catalogue and tiers are named by job. The cost the
        docstring cites is a measured figure of a run, not a price the code uses."""
        import inspect
        source = inspect.getsource(absence)
        for forbidden in ("tencent", "deepseek", "openai/", "anthropic/", "gpt-", "claude-"):
            assert forbidden not in source
