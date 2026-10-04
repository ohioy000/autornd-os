"""Ruling D50 (1): the recorded answers are the regression vectors.

The tier-2 scorer is repaired as a new version
(frozen-2026-10-03.1) before any paid tier-3 unit runs, because
the frozen scorer (frozen-2026-10-03) failed 7 of the twelve
real answers recorded in the committed measurement traces - it
read the answers' notation, not their content. This file wires
the two instruments that prove the repair into the suite:

- the twelve recorded vectors (evals/tier2/regression_12.py),
  read from the traces' own bytes and scored here: all twelve
  must pass, where five passed under the frozen version;
- the notation-variant sweep (evals/tier2/notation_sweep.py):
  every Q1-Q5 model answer rendered in every applicable variant
  form must still pass, and every wrong answer rendered in the
  same forms must still fail.

Both probes are provider-free and read only committed files. The
discrimination test proves the vector test is a measurement, not
a vacuous green: a wrong answer must score FAIL, so a scorer
that passed everything would fail this file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIER2 = ROOT / "evals" / "tier2"
sys.path.insert(0, str(TIER2))
import scorer  # noqa: E402
import regression_12  # noqa: E402
import notation_sweep  # noqa: E402

# The sweep's measured variant counts (2026-10-03, this scorer
# version): 52 model-answer variants, 42 wrong-answer variants.
# The sweep is deterministic, so these are exact guards: a
# renderer that stops producing variants (or a new form added
# deliberately) changes the count, and the change is reviewed
# with it.
MODEL_VARIANTS = 52
WRONG_VARIANTS = 42


class TestTheRecordedVectors:
    """The twelve real answers the recorded runs produced, scored
    by this package's scorer. Under the frozen version five of
    the twelve failed; under the repaired version all twelve
    hold."""

    def test_the_probe_registers_twelve_vectors(self):
        vectors = regression_12.load_vectors()
        assert len(vectors) == 12
        runs: dict[str, int] = {}
        for run, qid, answer in vectors:
            assert qid in ("Q1", "Q2", "Q3", "Q4", "Q5"), (
                f"the probe registered {qid}, outside the "
                f"swept set Q1-Q5")
            assert answer.strip(), (
                f"{run} {qid} carries an empty answer")
            runs[run] = runs.get(run, 0) + 1
        # The registered set: five direct answers from 107, four
        # pipeline answers from 102, three from 106.
        assert runs == {"107-direct": 5, "102": 4,
                        "106": 3}, runs

    def test_all_twelve_recorded_answers_pass(self):
        failures = []
        for run, qid, answer in regression_12.load_vectors():
            result = scorer.score(qid, answer)
            if result["verdict"] != "PASS":
                failures.append((
                    run, qid, result["verdict"],
                    [i["item"] for i in result["items"]
                     if not i["pass"]]))
        assert not failures, (
            f"{len(failures)}/12 recorded answers fail - "
            f"the scorer reads notation, not answers: "
            f"{failures}")

    def test_the_reading_discriminates(self):
        # Convention 22: an instrument's test must be able to
        # fail. A wrong answer the keys register must score FAIL
        # here, so the 12/12 result above is a measurement and
        # not a green that any answer would produce.
        keys = json.loads(
            (TIER2 / "keys.json").read_text(encoding="utf-8"))
        q1 = next(k for k in keys if k["id"] == "Q1")
        assert q1["common_wrong_answers"], (
            "Q1 registers no wrong answer to test with")
        for wrong in q1["common_wrong_answers"]:
            result = scorer.score("Q1", wrong["answer"])
            assert result["verdict"] == "FAIL", (
                f"the wrong answer {wrong['answer']!r} scores "
                f"{result['verdict']} - the reading cannot "
                f"discriminate")


class TestTheNotationSweep:
    """Every Q1-Q5 model answer in every applicable variant form
    must pass every required item, and every wrong answer in the
    same forms must still fail: a notation the scorer newly
    accepts must not accept a wrong answer stated in it."""

    @staticmethod
    def _record() -> dict:
        return notation_sweep.sweep()

    def test_every_model_answer_variant_passes(self):
        record = self._record()
        failures = []
        for qid in notation_sweep.SWEEPED:
            for form, verdict, passed, total in (
                    record[qid]["model"]):
                if verdict != "PASS":
                    failures.append(
                        (qid, form, passed, total))
        assert not failures, (
            "model answers rejected for their notation: "
            f"{failures}")

    def test_every_wrong_answer_variant_still_fails(self):
        record = self._record()
        accepted = []
        for qid in notation_sweep.SWEEPED:
            for answer, form, verdict in (
                    record[qid]["wrong"]):
                if verdict != "FAIL":
                    accepted.append((qid, form, answer))
        assert not accepted, (
            "wrong answers accepted in a newly accepted "
            f"notation: {accepted}")

    def test_the_sweep_renders_every_applicable_form(self):
        # The two tests above would pass vacuously if a renderer
        # stopped producing variants, so the sweep's own output is
        # guarded: the measured counts and the form set.
        record = self._record()
        model = sum(len(record[q]["model"])
                    for q in notation_sweep.SWEEPED)
        wrong = sum(len(record[q]["wrong"])
                    for q in notation_sweep.SWEEPED)
        assert model == MODEL_VARIANTS, (
            f"the sweep rendered {model} model-answer "
            f"variants, not the measured {MODEL_VARIANTS}")
        assert wrong == WRONG_VARIANTS, (
            f"the sweep rendered {wrong} wrong-answer "
            f"variants, not the measured {WRONG_VARIANTS}")
        forms = {form for q in notation_sweep.SWEEPED
                 for form, _v, _p, _t in record[q]["model"]}
        # Each renderer family must be represented in the union
        # of the four swept answers' variant sets.
        for family in ("bold headings", "plain-digit units",
                       "comma-grouped digits",
                       "unicode-superscript exponents",
                       "bulleted steps", "tabulated steps",
                       "rule line at the end",
                       "verdict before the figures",
                       "plain text"):
            assert family in forms, (
                f"the sweep rendered no variant in the "
                f"{family} form")
