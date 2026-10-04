"""The notation-variant sweep (Ruling D50 (1)).

The scorer must read an answer by its content, not
its notation: the recorded answers use different
heading styles, exponent and unit forms, digit
grouping, operator phrasings, step styles and
verdict placements, and a scorer that recognizes
only one notation recognizes the notation, not
the answer. This sweep renders every key's model
answer for tier-2 Q1-Q5 - the five questions the
twelve recorded regression vectors answer - and
every wrong answer the key registers for them, in
every variant form that applies:

- heading styles: markdown '##', bold '**',
  italic '*', labeled 'Heading:' and numbered
  '1.' forms of every heading line,
- exponent forms: the LaTeX caret form rendered
  as unicode superscripts ('6.14×10⁻⁷'), as
  e-notation ('6.14e-7') and as 'x 10^-7',
- unit forms: 'mm^2' rendered as 'mm²' and as
  the plain digit 'mm2',
- digit grouping: '30000' rendered as '30,000'
  and '30 000',
- operator phrasings: every comparison operator
  rendered as each synonym of its own strictness
  class ('≤' as 'at most', 'no more than',
  'must not exceed', ...; '<' as 'less than',
  'below', 'under'),
- step styles: numbered steps rendered as
  bullets, '**Step N —**' lines, '### Step N —'
  lines, sub-numbered 'N.1.' lines and a
  markdown table,
- the verdict stated before the figures and
  after them, with a conditional rule line
  inserted at the start, the middle and the end,
- the LaTeX forms rendered as plain text.

Every model-answer variant must pass every
required item, and every wrong-answer variant
must still fail: a notation the scorer newly
accepts must not accept a wrong answer stated in
it. The sweep reads the keys and the scorer from
this package's own files - no network, no
provider - and prints the counts:

    .venv/bin/python3 evals/tier2/notation_sweep.py

Exit status: 0 if every variant holds, 1 if any
model-answer variant fails or any wrong-answer
variant passes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scorer  # noqa: E402

KEYS = json.loads((HERE / "keys.json").read_text(
    encoding="utf-8"))
SWEEPED = ("Q1", "Q2", "Q3", "Q4", "Q5")


# ── heading styles ────────────────────────────────────

def _heading_text(line: str) -> str:
    """The text of a heading line, with every
    heading decoration stripped."""
    text = line.strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^\d+\.\s*", "", text)
    text = re.sub(r"^[Hh]eading:\s*", "", text)
    for open_, close in (("\\*\\*", "\\*\\*"),
                         ("__", "__"),
                         ("\\*", "\\*"),
                         ("_", "_")):
        text = re.sub(rf"^{open_}([^{close}]+)"
                      rf"{close}$", r"\1", text)
    return text.strip()


def _restyle_headings(text: str,
                      style) -> str | None:
    """Every heading line re-rendered in one
    heading style. None when the answer carries
    no heading line."""
    lines = text.splitlines()
    if not any(scorer._HEADING.match(l)
               for l in lines):
        return None
    out: list[str] = []
    number = 0
    for line in lines:
        if scorer._HEADING.match(line):
            number += 1
            out.append(style(_heading_text(line),
                             number))
        else:
            out.append(line)
    return "\n".join(out)


_HEADING_STYLES = (
    ("markdown headings",
     lambda t, _n: f"## {t}"),
    ("bold headings",
     lambda t, _n: f"**{t}**"),
    ("italic headings",
     lambda t, _n: f"*{t}*"),
    ("labeled headings",
     lambda t, _n: f"Heading: {t}"),
    ("numbered headings",
     lambda t, n: f"{n}. {t}"),
)


# ── exponent forms ────────────────────────────────────

_EXPONENT = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\\times|×|x|\*)\s*"
    r"10\s*\^\s*\{?\s*(-?\d+)\s*\}?")
_SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹"


def _superscript(digits: str) -> str:
    out = ""
    for c in digits:
        if c == "-":
            out += "⁻"
        else:
            out += _SUPERSCRIPT[int(c)]
    return out


def _render_exponent(text: str,
                     form) -> str | None:
    """Every mantissa-times-ten-to-an-exponent
    re-rendered in one exponent form. None when
    the answer states no such value."""
    if not _EXPONENT.search(text):
        return None
    if form == "superscript":
        return _EXPONENT.sub(
            lambda m: (f"{m.group(1)}×10"
                       f"{_superscript(m.group(2))}"),
            text)
    if form == "e-notation":
        return _EXPONENT.sub(
            lambda m: f"{m.group(1)}e{m.group(2)}",
            text)
    return _EXPONENT.sub(
        lambda m: (f"{m.group(1)} x "
                   f"10^{m.group(2)}"),
        text)


_EXPONENT_FORMS = (
    ("unicode-superscript exponents",
     "superscript"),
    ("e-notation exponents", "e-notation"),
    ("x-caret exponents", "x-caret"),
)


# ── unit forms ────────────────────────────────────────

_UNIT_EXPONENT = re.compile(
    r"\b([A-Za-z]+)\^(\d)\b")
_UNIT_DIGITS = {"1": "¹", "2": "²", "3": "³",
                "4": "⁴", "5": "⁵", "6": "⁶",
                "7": "⁷", "8": "⁸", "9": "⁹",
                "0": "⁰"}


def _render_unit(text: str,
                 form) -> str | None:
    """Every unit-with-exponent re-rendered in one
    unit form. None when the answer states no such
    unit."""
    if not _UNIT_EXPONENT.search(text):
        return None
    if form == "superscript":
        return _UNIT_EXPONENT.sub(
            lambda m: (f"{m.group(1)}"
                       f"{_UNIT_DIGITS[m.group(2)]}"),
            text)
    return _UNIT_EXPONENT.sub(
        lambda m: f"{m.group(1)}{m.group(2)}",
        text)


_UNIT_FORMS = (
    ("unicode-superscript units", "superscript"),
    ("plain-digit units", "plain-digit"),
)


# ── digit grouping ────────────────────────────────────

_GROUPED = re.compile(r"\b(\d{5,})\b")


def _render_grouping(text: str,
                     separator: str) -> str | None:
    """Every integer of five or more digits
    re-rendered with a grouping separator. None
    when the answer states no such integer."""
    if not _GROUPED.search(text):
        return None

    def group(m: re.Match) -> str:
        digits = m.group(1)
        parts = []
        while len(digits) > 3:
            parts.insert(0, digits[-3:])
            digits = digits[:-3]
        parts.insert(0, digits)
        return separator.join(parts)

    return _GROUPED.sub(group, text)


_GROUPING_FORMS = (
    ("comma-grouped digits", ","),
    ("space-grouped digits", " "),
)


# ── operator phrasings ────────────────────────────────

# Every comparison operator the keys state, with
# the synonyms of its own strictness class: a
# rendering never changes what is stated, only
# how it is stated.
_OPERATOR_FORMS = (
    (re.compile(r"\\leq|≤|<="),
     ("≤", "<=", "at most", "no more than",
      "must not exceed", "does not exceed",
      "up to and including", "at or below",
      "no greater than")),
    (re.compile(r"\\geq|≥|>="),
     ("≥", ">=", "at least", "at or above",
      "no less than")),
    (re.compile(r"(?<![<=\\])<(?![=>])"),
     ("<", "less than", "below", "under")),
    (re.compile(r"(?<![>=\\])>(?![=>])"),
     (">", "more than", "above",
      "greater than")),
    (re.compile(r"\bat or below\b|\bor less\b|"
                r"\bno more than\b|\bat most\b|"
                r"\bmust not exceed\b|"
                r"\bdoes not exceed\b|"
                r"\bup to and including\b|"
                r"\bno greater than\b"),
     ("at most", "no more than", "must not exceed",
      "does not exceed", "up to and including",
      "at or below", "no greater than", "≤",
      "<=")),
    (re.compile(r"\bat or above\b|\bor more\b|"
                r"\bat least\b|\bno less than\b"),
     ("at least", "at or above", "no less than",
      "≥", ">=")),
    (re.compile(r"\bless than\b|\bbelow\b|"
                r"\bunder\b"),
     ("less than", "below", "under", "<")),
    (re.compile(r"\bmore than\b|\babove\b|"
                r"\bgreater than\b|\bover\b"),
     ("more than", "above", "greater than",
      "over", ">")),
)


def _render_operators(text: str) -> list[str]:
    """Every comparison operator re-rendered as
    each synonym of its own strictness class -
    one variant per synonym."""
    variants: list[str] = []
    for pattern, synonyms in _OPERATOR_FORMS:
        if not pattern.search(text):
            continue
        for synonym in synonyms:
            if synonym in text:
                continue
            spaced = (f" {synonym} "
                      if synonym.isalpha()
                      else synonym)
            variants.append(
                pattern.sub(spaced, text))
    return variants


# ── step styles ───────────────────────────────────────

_STEP = re.compile(r"^\s*(\d+)\.\s+(.*)$")


def _render_steps(text: str,
                  style) -> str | None:
    """Every numbered step re-rendered in one
    step style. None when the answer carries no
    numbered step list."""
    lines = text.splitlines()
    if sum(1 for l in lines
           if _STEP.match(l)) < 2:
        return None
    out: list[str] = []
    for line in lines:
        m = _STEP.match(line)
        if m:
            out.append(style(m.group(1),
                             m.group(2)))
        else:
            out.append(line)
    return "\n".join(out)


_STEP_STYLES = (
    ("bulleted steps",
     lambda _n, body: f"- {body}"),
    ("bold step lines",
     lambda n, body: f"**Step {n} —** {body}"),
    ("markdown step lines",
     lambda n, body: f"### Step {n} — {body}"),
    ("sub-numbered steps",
     lambda n, body: f"{n}.1. {body}"),
)


def _render_step_table(text: str) -> str | None:
    """The numbered step list rendered as a
    markdown table, the first step line replaced
    by the table and the rest dropped. None when
    the answer carries no numbered step list."""
    lines = text.splitlines()
    steps = [m for m in (_STEP.match(l)
                         for l in lines) if m]
    if len(steps) < 2:
        return None
    table = ["| Step | Action |",
             "|------|--------|"]
    for m in steps:
        table.append(f"| {m.group(1)} "
                     f"| {m.group(2)} |")
    out: list[str] = []
    dropped = False
    for line in lines:
        if _STEP.match(line):
            if not dropped:
                out.extend(table)
                dropped = True
            continue
        out.append(line)
    return "\n".join(out)


# ── the verdict's placement ───────────────────────────

_VERDICT_WORD = re.compile(
    r"\b(?:pass|fail|acceptable|unacceptable)\b")
_RULE_LINE = ("If either criterion fails, the "
              "verdict is FAIL.")


def _stated_verdict_word(text: str) -> str | None:
    """The answer's own last verdict word, read
    the way the scorer reads it: outside a
    conditional clause."""
    low = scorer._normalize(text).lower()
    last = None
    for line in low.splitlines():
        for m in re.finditer(
                r"\b(?:unacceptable|acceptable|"
                r"fail|pass)\b", line):
            if scorer._CONDITIONAL.search(
                    line[max(0, m.start() - 40):
                         m.start()]):
                continue
            last = m.group(0)
    if last is None:
        return None
    return ("PASS" if last in ("pass",
                               "acceptable")
            else "FAIL")


def _render_verdict(text: str,
                    placement) -> str | None:
    """The answer's stated verdict restated before
    the figures and after them. None when the
    answer states no verdict."""
    word = _stated_verdict_word(text)
    if word is None:
        return None
    if placement == "before":
        return f"Verdict: {word}.\n" + text
    return text + f"\nVerdict: {word}."


def _render_rule_line(text: str,
                      placement) -> str | None:
    """A conditional rule line inserted at the
    start, the middle and the end of the answer.
    None when the answer states no verdict word
    for the rule to condition."""
    if not _VERDICT_WORD.search(
            scorer._normalize(text).lower()):
        return None
    if placement == "start":
        return _RULE_LINE + "\n" + text
    if placement == "middle":
        lines = text.splitlines()
        at = len(lines) // 2
        return "\n".join(
            lines[:at] + [_RULE_LINE]
            + lines[at:])
    return text + "\n" + _RULE_LINE


# ── plain text ────────────────────────────────────────

def _render_plain(text: str) -> str | None:
    """The LaTeX forms rendered as plain text.
    None when the answer carries no LaTeX."""
    if "$" not in text and "\\" not in text:
        return None
    out = text
    out = re.sub(r"\\mathrm\{([^}]*)\}",
                 r"\1", out)
    out = re.sub(r"\\text\{([^}]*)\}", r"\1",
                 out)
    out = out.replace("\\,", " ")
    out = out.replace("\\;", " ")
    out = out.replace("\\ ", " ")
    out = out.replace("\\%", "%")
    out = out.replace("\\times", "×")
    out = out.replace("\\leq", "≤")
    out = out.replace("\\geq", "≥")
    out = out.replace("\\pi", "pi")
    out = out.replace("$", "")
    return out


# ── the sweep ─────────────────────────────────────────

def _variants(text: str) -> list[tuple[str, str]]:
    """Every variant form that applies to one
    answer, as (form, rendered text)."""
    out: list[tuple[str, str]] = []
    for name, style in _HEADING_STYLES:
        rendered = _restyle_headings(text, style)
        if rendered is not None:
            out.append((name, rendered))
    for name, form in _EXPONENT_FORMS:
        rendered = _render_exponent(text, form)
        if rendered is not None:
            out.append((name, rendered))
    for name, form in _UNIT_FORMS:
        rendered = _render_unit(text, form)
        if rendered is not None:
            out.append((name, rendered))
    for name, separator in _GROUPING_FORMS:
        rendered = _render_grouping(text, separator)
        if rendered is not None:
            out.append((name, rendered))
    for rendered in _render_operators(text):
        out.append(("operator phrasing", rendered))
    for name, style in _STEP_STYLES:
        rendered = _render_steps(text, style)
        if rendered is not None:
            out.append((name, rendered))
    rendered = _render_step_table(text)
    if rendered is not None:
        out.append(("tabulated steps", rendered))
    for placement in ("before", "after"):
        rendered = _render_verdict(text, placement)
        if rendered is not None:
            out.append((f"verdict {placement} the "
                        f"figures", rendered))
    for placement in ("start", "middle", "end"):
        rendered = _render_rule_line(text, placement)
        if rendered is not None:
            out.append((f"rule line at the "
                        f"{placement}", rendered))
    rendered = _render_plain(text)
    if rendered is not None:
        out.append(("plain text", rendered))
    return out


def sweep() -> dict:
    """Run the sweep. Returns the per-question
    record: model-answer variants (all of which
    must pass) and wrong-answer variants (all of
    which must fail)."""
    record: dict = {}
    for rec in KEYS:
        qid = rec["id"]
        if qid not in SWEEPED:
            continue
        questions: dict = {"model": [],
                           "wrong": []}
        for form, variant in _variants(
                rec["model_answer"]):
            result = scorer.score(qid, variant)
            questions["model"].append(
                (form, result["verdict"],
                 result["passed_items"],
                 result["total_items"]))
        for wrong in rec.get(
                "common_wrong_answers", []):
            for form, variant in _variants(
                    wrong["answer"]):
                result = scorer.score(qid, variant)
                questions["wrong"].append(
                    (wrong["answer"][:40], form,
                     result["verdict"]))
        record[qid] = questions
    return record


def main(argv: list[str] | None = None) -> int:
    record = sweep()
    model_total = model_pass = 0
    wrong_total = wrong_fail = 0
    for qid in SWEEPED:
        questions = record[qid]
        model = questions["model"]
        wrong = questions["wrong"]
        model_total += len(model)
        model_pass += sum(1 for _f, v, _p, _t
                          in model if v == "PASS")
        wrong_total += len(wrong)
        wrong_fail += sum(1 for _a, _f, v in wrong
                          if v == "FAIL")
        model_here = sum(1 for _f, v, _p, _t
                           in model if v == "PASS")
        forms = sorted({f for f, _v, _p, _t
                        in model})
        print(f"{qid} model answer: "
              f"{model_here}/{len(model)} variants "
              f"pass ({', '.join(forms)})")
        for form, verdict, passed, total in model:
            if verdict != "PASS":
                print(f"    FAIL  {form}: "
                      f"{passed}/{total} items")
        wrong_forms = sorted({f for _a, f, _v
                              in wrong})
        wrong_here = sum(1 for _a, _f, v in wrong
                           if v == "FAIL")
        print(f"{qid} wrong answers: "
              f"{wrong_here}/{len(wrong)} variants "
              f"fail ({', '.join(wrong_forms)})")
        for answer, form, verdict in wrong:
            if verdict != "FAIL":
                print(f"    PASS  {answer!r} "
                      f"under {form}")
    print()
    if model_pass == model_total and \
            wrong_fail == wrong_total:
        print(f"NOTATION SWEEP PASSED: "
              f"{model_total} model-answer variants "
              f"all pass, {wrong_total} wrong-answer "
              f"variants all fail, under scorer "
              f"version {scorer.SCORER_VERSION}")
        return 0
    print(f"NOTATION SWEEP FAILED: "
          f"{model_pass}/{model_total} model-answer "
          f"variants pass, {wrong_fail}/{wrong_total} "
          f"wrong-answer variants fail")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
