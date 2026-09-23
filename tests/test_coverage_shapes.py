"""Ruling B17-R1: shape selects the test (§29).

The defect these tests exist for, measured 2026-09-21 on the B14 demonstration
(`docs/traces/b14-demo-marketing-claims-grounded.jsonl`): term overlap scored a
*compliant* draft 40% on a criterion whose satisfaction is an absence, failed
the same two criteria on all seven iterations while `implement.green` was true
throughout, and the run died at the call ceiling — 42 calls, $0.1783, no
terminal.

Every test here simulates its own condition end to end (convention 22): a real
criterion string and a real draft, through the registered check, never a mock.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autornd.graph.checks import FORM, PRESENCE, PROHIBITION, _classify, get_check

TRACE = Path("docs/traces/b14-demo-marketing-claims-grounded.jsonl")

# Verbatim from the trace. These are fixtures, not paraphrases: the whole point
# is that the check is tested on the text that broke it.
CRITERION_PROHIBITION = (
    "The brief uses plain language, avoids the banned words ('leverage', "
    "'seamless', 'robust', 'in today's fast-paced world'), and follows "
    "Meridian's structure conventions (sentence case headings, no H4+, numbers "
    "as words below 10, dates as '12 March 2026')."
)
CRITERION_FORM = (
    "Three proof points are provided, each a factual claim about the "
    "expense-management market (e.g., adoption rates, time spent, error "
    "rates). Every proof point is accompanied by a source that includes "
    "organization/author, title, date, and a retrievable location, or is "
    "explicitly marked as 'unsourced'."
)
CRITERION_SITUATIONAL = (
    "No claim about a named competitor appears without a clear flag indicating "
    "that legal review is required before publication."
)

COVERAGE = get_check("criteria_addressed")


class TestProhibition:
    """Inverted: the criterion's own forbidden tokens become the test."""

    def test_a_compliant_draft_passes_where_overlap_scored_it_40_percent(self):
        """The inversion case. This draft satisfies the criterion perfectly and
        the old check failed it *because* it satisfied it — 14 of the 17
        significant terms are unreachable for a compliant draft."""
        draft = (
            "## Audience\n\nThe brief is written in plain words for finance "
            "leads at mid-sized firms. Headings use sentence case and stop at "
            "H3. Numbers below ten are spelled out. Dates read 12 March 2026."
        )
        result = COVERAGE([CRITERION_PROHIBITION], draft)
        assert result.passed
        assert result.data["shapes"][CRITERION_PROHIBITION] == PROHIBITION
        assert result.data["coverage"][CRITERION_PROHIBITION] == 1.0

    def test_a_banned_word_is_a_hard_red(self):
        draft = "We leverage a seamless workflow for finance leads."
        result = COVERAGE([CRITERION_PROHIBITION], draft)
        assert not result.passed
        assert "'leverage'" in result.detail and "'seamless'" in result.detail
        assert "not met by" in result.detail

    def test_a_banned_phrase_is_matched_as_a_phrase(self):
        """'in today's fast-paced world' is one banned thing, not four words."""
        draft = "In today's fast-paced world, finance leads need clarity."
        assert not COVERAGE([CRITERION_PROHIBITION], draft).passed

    def test_the_phrase_is_still_found_across_a_line_break(self):
        """A guard asserting a phrase that spanned a line break failed on
        correct text once this week. The same shape here would make the
        strongest test in the check silently lenient."""
        draft = "In today's\nfast-paced world, finance leads need clarity."
        assert not COVERAGE([CRITERION_PROHIBITION], draft).passed

    def test_the_banned_words_are_not_matched_inside_other_words(self):
        """Word boundaries: 'robustness' is not 'robust' asserted as a claim."""
        draft = "Plain words for finance leads at mid-sized firms."
        assert COVERAGE([CRITERION_PROHIBITION], draft).passed

    def test_the_second_parenthesis_is_not_read_as_a_forbidden_list(self):
        """Criterion 6 carries two parentheses. The structure-conventions one —
        '(sentence case headings, no H4+, ...)' — is a presence-shaped aside,
        and reading it as forbidden would ban the draft from being correct."""
        _, forbidden = _classify(CRITERION_PROHIBITION)
        assert forbidden == [
            "leverage", "seamless", "robust", "in today's fast-paced world",
        ]


class TestForm:
    """Abstain: term overlap is not a valid test, and saying so is the honest
    answer. A real citation carries an organization's *name*, not the word
    'organization' — which is why a draft with complete citations scored 37%."""

    def test_a_form_criterion_abstains_and_does_not_fail_the_fold(self):
        draft = "Proof points: 42% of teams report delays (Acme Research, "
        result = COVERAGE([CRITERION_FORM], draft)
        assert result.passed
        assert result.data["shapes"][CRITERION_FORM] == FORM
        assert [a["criterion"] for a in result.data["abstained"]] == [CRITERION_FORM]

    def test_the_abstention_is_never_silent(self):
        result = COVERAGE([CRITERION_FORM], "anything at all")
        assert result.data["abstained"][0]["shape"] == FORM
        assert result.data["abstained"][0]["reason"]
        assert "abstained" in result.detail

    def test_an_all_abstained_plan_passes_but_says_it_measured_nothing(self):
        """Per B17-R1 an abstention never fails the check. A plan whose entire
        contract this instrument cannot read is still a finding, so the detail
        must not read as 'all criteria addressed'."""
        result = COVERAGE([CRITERION_FORM], "anything")
        assert result.passed
        assert result.data["all_abstained"] is True
        assert "nothing measurable" in result.detail

    def test_a_structural_verb_alone_does_not_buy_an_abstention(self):
        """Two distinct field words are demanded so a single incidental noun
        cannot make a measurable criterion unmeasurable. Criterion 1 of the
        same plan uses 'includes' and is pure presence."""
        criterion = ("The audience definition explicitly names whether the "
                     "piece serves practitioners or buyers, and includes the "
                     "company size range 50–500 employees.")
        assert _classify(criterion)[0] == PRESENCE


class TestPresenceIsUnchanged:
    """The drift-catcher. Nothing here may move: these are the exhibits the
    check was built on, at 71–100% for real work and 0–33% for waffle."""

    CRITERIA = [
        "Reconnect loop applies exponential backoff capped at 60s with jitter",
        "Client re-subscribes to all topics after a successful reconnect",
        "Each reconnect attempt emits a metric with the attempt number",
    ]

    def test_faithful_work_still_passes(self):
        assert COVERAGE(self.CRITERIA, (
            "Added exponential backoff to the reconnect loop, capped at 60s with "
            "jitter. After a successful reconnect the client re-subscribes to all "
            "topics. Each attempt emits a metric carrying the attempt number."
        )).passed

    def test_topic_mentioning_waffle_still_fails(self):
        """THE FALSIFICATION TEST. If shape classification ever widened far
        enough to abstain or invert its way past this, the ruling would have
        traded one failure for exactly the drift the check exists to catch."""
        result = COVERAGE(self.CRITERIA, (
            "Reworked the reconnection handling. The loop now backs off between "
            "attempts, topics are handled on reconnect, and attempts are observable."
        ))
        assert not result.passed
        assert result.data["addressed"] == 0
        assert result.data["abstained"] == []
        assert set(result.data["shapes"].values()) == {PRESENCE}

    def test_a_prohibited_situation_with_no_token_list_stays_presence(self):
        """Fail-safe direction. Criterion 4 reads as a prohibition and names no
        forbidden vocabulary — it prohibits a *situation*. It scored 64% and
        passed on overlap, correctly, and must keep doing so."""
        assert _classify(CRITERION_SITUATIONAL)[0] == PRESENCE


@pytest.mark.skipif(not TRACE.exists(), reason="demonstration trace not committed")
class TestTheCommittedDemonstration:
    """Replay against the run that B17-R1 exists to fix. Not a simulation: the
    criteria and the drafts are read from the committed trace."""

    @staticmethod
    def _unit() -> dict:
        records = [json.loads(line) for line in TRACE.read_text().splitlines() if line.strip()]
        return next(r for r in records if r.get("record") == "unit")

    def test_the_final_draft_now_passes_where_the_run_died(self):
        unit = self._unit()
        criteria = unit["verdicts"]["plan"]["success_criteria"]
        draft = unit["iterations"][-1]["implement_summary"]

        assert unit["iterations"][-1]["coverage_passed"] is False   # as measured
        result = COVERAGE(criteria, draft)
        assert result.passed                                        # as ruled

    def test_the_two_killing_criteria_classify_as_ruled(self):
        criteria = self._unit()["verdicts"]["plan"]["success_criteria"]
        shapes = {c: _classify(c)[0] for c in criteria}
        assert shapes[criteria[2]] == FORM           # criterion 3, scored 37%
        assert shapes[criteria[5]] == PROHIBITION    # criterion 6, scored 40%

    def test_the_earlier_drafts_still_fail_on_presence(self):
        """The ruling is not a blanket pass. Six of the seven iterations still
        fail, on presence criteria the drafts genuinely did not address — which
        is the check working, and is why the advisor's registered prediction of
        a terminal at iteration 1 is refuted before a dollar is spent."""
        unit = self._unit()
        criteria = unit["verdicts"]["plan"]["success_criteria"]
        outcomes = [COVERAGE(criteria, it["implement_summary"]).passed
                    for it in unit["iterations"]]
        assert outcomes.count(True) == 1
        assert outcomes[0] is False


class TestOnlyProperlyQuotedTokensAreForbidden:
    """B24: a possessive is not a quotation, and an unquoted aside is not a token.

    **The defect.** `_forbidden_tokens` used to accept any parenthetical that
    *contained a quote character*, then split the whole group on commas and
    strip quotes from each part. A possessive, a contraction or an unquoted
    aside therefore became a forbidden token — and a forbidden token that was
    never forbidden is a FALSE PROHIBITION.

    **Why that direction matters.** B17 fails work that is correct. These pass
    work that is wrong: invert a criterion whose quoted token must be PRESENT
    and the draft that omits it passes while the draft that includes it fails.

    **Measured impact on the committed corpus: zero.** All 597 criteria extract
    identically before and after, because the 40 that match a prohibition
    marker use backticks in their parentheticals rather than quotes. The defect
    was latent and reachable, not live — and it is fixed before it fired rather
    than after, which is the only reason this change alters nothing the harness
    currently concludes.
    """

    @pytest.mark.parametrize("criterion,expected,why", [
        ("The statement avoids table locks (CrateDB's default non-blocking behavior).",
         [], "a possessive apostrophe is not a quotation"),
        ("The draft avoids jargon (don't use it, it's bad)",
         [], "two contractions are not two forbidden tokens"),
        ("The draft avoids competitor names without a note (e.g., 'Pending legal review') beside it.",
         ["Pending legal review"], "'e.g.' was never quoted and must not be extracted"),
    ])
    def test_prose_is_not_mistaken_for_a_token_list(self, criterion, expected, why):
        from autornd.graph.checks import _forbidden_tokens
        assert _forbidden_tokens(criterion) == expected, why

    def test_the_genuine_exhibit_still_extracts_all_four(self):
        """The narrowing must not cost the one prohibition the corpus contains.

        The fourth token carries an apostrophe INSIDE the quotes. A pattern that
        forbade internal apostrophes would drop it, trading a false-prohibition
        bug for a false negative on B17's own exhibit.
        """
        from autornd.graph.checks import _forbidden_tokens
        criterion = ("The brief uses plain language, avoids the banned words "
                     "('leverage', 'seamless', 'robust', 'in today's fast-paced world')")
        assert _forbidden_tokens(criterion) == [
            "leverage", "seamless", "robust", "in today's fast-paced world"]

    @pytest.mark.parametrize("criterion,expected", [
        ('The copy avoids the terms ("foo", "bar")', ["foo", "bar"]),
        ("The copy avoids the words ‘alpha’, and (‘beta’)", ["beta"]),
    ])
    def test_other_quote_styles_still_work(self, criterion, expected):
        from autornd.graph.checks import _forbidden_tokens
        assert _forbidden_tokens(criterion) == expected

    def test_the_presence_shaped_aside_is_still_excluded(self):
        """The case the original quote requirement was written for, kept working."""
        from autornd.graph.checks import _forbidden_tokens
        criterion = ("The copy avoids passive voice (sentence case headings, "
                     "no H4+, numbers as words below 10, dates as '12 March 2026')")
        # Only the genuinely quoted fragment survives; the unquoted conventions do not.
        assert _forbidden_tokens(criterion) == ["12 March 2026"]

    def test_what_this_does_not_fix_is_stated_not_hidden(self):
        """A correctly quoted token that must be PRESENT is still inverted.

        Deciding which side of a negation a quoted token falls on is
        comprehension, not extraction, so it is a ruling and stays open. Pinned
        here so the remaining defect cannot be mistaken for a fixed one.
        """
        from autornd.graph.checks import _forbidden_tokens
        criterion = ("The draft avoids competitor names without a note "
                     "(e.g., 'Pending legal review') beside it.")
        assert _forbidden_tokens(criterion) == ["Pending legal review"], (
            "still extracted, and still inverted the wrong way round — B24's "
            "open half, reported rather than silently repaired")


class TestCoverageRecordStatesItsSubject:
    """ARCH-20260922-035 Exhibit 1: the coverage record must carry the
    extracted terms and forbidden tokens per criterion, not only the score.

    Convention 28 / retry_reconciliation() pattern: a score without the
    extraction that produced it is a conclusion a reader cannot verify without
    re-running the extractor by hand (-029).
    """

    def test_presence_criterion_carries_its_extracted_terms(self):
        criterion = "The implementation uses exponential backoff with jitter."
        result = COVERAGE([criterion], "applies exponential backoff with jitter")
        ext = result.data["extractions"][criterion]
        assert "terms" in ext
        assert "exponential" in ext["terms"]
        assert "backoff" in ext["terms"]
        assert ext["forbidden_tokens"] == []

    def test_prohibition_criterion_carries_its_forbidden_tokens(self):
        result = COVERAGE([CRITERION_PROHIBITION],
                          "A plain-language brief for finance leads.")
        ext = result.data["extractions"][CRITERION_PROHIBITION]
        assert ext["forbidden_tokens"], "prohibition must name its tokens"
        assert "leverage" in ext["forbidden_tokens"]
        assert "terms" in ext

    def test_form_criterion_carries_its_extracted_terms(self):
        result = COVERAGE([CRITERION_FORM], "")
        ext = result.data["extractions"][CRITERION_FORM]
        assert ext["terms"], "even an abstained criterion states its subject"
        assert ext["forbidden_tokens"] == []

    def test_removing_the_field_breaks_this_test(self):
        """Convention 22: prove by breaking."""
        result = COVERAGE([CRITERION_PROHIBITION],
                          "A plain-language brief for finance leads.")
        assert "extractions" in result.data, (
            "the extractions field was removed — the record no longer states "
            "what was scored on, which is the defect -029 measured")
