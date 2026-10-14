"""The anchor floor, pinned from both sides (Ruling D51 (1), (3)).

A quote anchors only when the free check finds it in the request
under the normalisation the checks already apply, and it clears
the floor: at least three words and twelve characters after
normalisation. The advisor proposed that floor; these tests pin
it so a future change to it cannot pass silently in either
direction — a floor that admits too little anchors by accident
(any request of a dozen words contains "the answer" somewhere),
and a floor that admits too much demotes real asks.

Every test drives the real primitives the phases and the checks
share — `quote_anchors` and the `asks_anchored` check — not a
copy, so the pinning covers the code that runs.
"""

import pytest

from autornd.graph.checks import asks_anchored, quote_anchors
from autornd.models.verdicts import (
    UNANCHORED_ASK_QUOTE,
    normalisations_by_kind,
    reset_normalisations,
)


# A quote sitting exactly on the floor: three words, twelve
# characters after normalisation ("abc defg hij" is 3+1+4+1+3).
AT_FLOOR = "abc defg hij"
AT_FLOOR_REQUEST = "The answer must use abc defg hij throughout."


@pytest.fixture(autouse=True)
def _reset_counts():
    reset_normalisations()
    yield
    reset_normalisations()


class TestTheFloorHoldsBothSides:
    def test_a_quote_on_the_floor_anchors(self):
        assert len(AT_FLOOR.split()) == 3
        assert len(AT_FLOOR) == 12
        assert quote_anchors(AT_FLOOR, AT_FLOOR_REQUEST)

    def test_one_word_short_of_the_floor_does_not_anchor(self):
        # Same character count, two words instead of three.
        short = "abc defghijk"
        assert len(short.split()) == 2
        assert len(short) == 12
        assert not quote_anchors(short, AT_FLOOR_REQUEST)

    def test_one_character_short_of_the_floor_does_not_anchor(self):
        # Still three words, eleven characters.
        short = "abc defg hi"
        assert len(short.split()) == 3
        assert len(short) == 11
        assert not quote_anchors(short, AT_FLOOR_REQUEST)

    def test_the_ruling_s_own_example_does_not_anchor(self):
        assert not quote_anchors("mm", "measure in mm please")


class TestTheNormalisationAnchorsThrough:
    """Case, whitespace and the LaTeX '$' wrapper are folded away,
    so a quote wrapped for math mode anchors the words it wraps."""

    @pytest.mark.parametrize("quote", [
        "ABC DEFG HIJ",                       # case-folded
        "abc   defg\thij",                    # whitespace collapsed
        "$abc defg hij$",                     # LaTeX wrapper stripped
        "  Abc Defg Hij  ",                   # all three at once
    ])
    def test_a_quote_that_is_the_request_s_words_anchors(self, quote):
        assert quote_anchors(quote, AT_FLOOR_REQUEST)

    def test_a_paraphrase_does_not_anchor(self):
        assert not quote_anchors(
            "must use abc defg hij throughout", AT_FLOOR_REQUEST.replace(
                "The answer must use", "You should apply"))

    def test_a_quote_absent_from_the_request_does_not_anchor(self):
        assert not quote_anchors(
            "abc defg hij", "an unrelated request entirely")


class TestTheCheckAnchorsAndCounts:
    def test_a_verbatim_quote_anchors_with_its_kind(self):
        result = asks_anchored(
            [{"quote": AT_FLOOR, "kind": "constraint"}],
            AT_FLOOR_REQUEST)
        assert result.passed
        assert result.data["anchored"] == [
            {"number": 1, "quote": AT_FLOOR, "kind": "constraint"}]
        assert result.data["quotes"] == [AT_FLOOR]
        assert result.data["demoted"] == []

    def test_every_demotion_is_counted(self):
        asks_anchored(
            [{"quote": "a paraphrase of the request", "kind": "value"},
             {"quote": "mm", "kind": "value"}],
            AT_FLOOR_REQUEST)
        counts = normalisations_by_kind()
        assert counts.get(UNANCHORED_ASK_QUOTE) == 2

    def test_when_nothing_anchors_the_request_is_the_one_ask(self):
        request = "Add retry with exactly 100 connections."
        result = asks_anchored(
            [{"quote": "paraphrased beyond the words", "kind": "step"}],
            request)
        assert result.data["anchored"] == [
            {"number": 1, "quote": request, "kind": ""}]
        assert result.data["quotes"] == [request]
        assert len(result.data["demoted"]) == 1
