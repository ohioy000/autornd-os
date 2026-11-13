"""Break each rule tier-2 scorer frozen-2026-10-03.4 adds, one at a
time, and show that the self-test fixture written for it fails.

Provider-free and offline. Run from the repository root:

    .venv/bin/python3 docs/probes/tier2_scorer_v4_breakproof.py

Each break copies evals/tier2 to a scratch directory, replaces one line
of the copy's scorer.py (the replacement must apply exactly once), runs
the copy's self-test, and checks that the named fixtures are among the
failures. The tree itself is never touched.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER2 = ROOT / "evals" / "tier2"

# (the rule, the line as it stands, the broken line, fixtures that must fail)
BREAKS: list[tuple[str, str, str, list[str]]] = [
    ("a line set between rules is a heading",
     r'''    r"|[-=~]{2,}\s*\S[^\n]*?\S\s*[-=~]{2,}\s*$)")''',
     r'''    r")")''',
     ["Q4 headings set between rules"]),
    ("a plain title line opens a section",
     r'''                and _PLAIN_TITLE.match(title)):''',
     r'''                and False and _PLAIN_TITLE.match(title)):''',
     ["Q4 plain title lines"]),
    ("'N*m' and 'N.m' are the spaced product",
     r'''    text = re.sub(r"(\d\s*[A-Za-z]{1,3})[*.]([A-Za-z]{1,3})"''',
     r'''    text = re.sub(r"(\d\s*[A-Za-z]{1,3})[#]([A-Za-z]{1,3})"''',
     ["Q18 moment in N*m", "Q18 moment in N.m and kN.m"]),
    ("'\\cdot' is the middle dot",
     r'''    text = re.sub(r"\s*\\cdot\s*", "·", text)''',
     r'''    text = re.sub(r"\s*\\cdot\s*", "  ", text)''',
     ["Q18 moment in N\\cdot m"]),
    ("an ellipsis does not part a number from its unit",
     r'''    text = re.sub(r"(\d)\s*(?:\\ldots|\\dots|\.\.\.|…)", r"\1",''',
     r'''    text = re.sub(r"(\d)\s*(?:QQQQ)", r"\1",''',
     ["Q19 repeating-decimal currents and comparisons beside "
      "the figure"]),
    ("the ratio written '3.00:1'",
     r'''             or re.search(r"(?<![\d.])3(?:\.0+)?\s*:\s*1"''',
     r'''             or None and re.search(r"(?<![\d.])3(?:\.0+)?\s*:\s*1"''',
     ["Q24 ratio as 3.00:1"]),
    ("'3.00:1' does not run on into more digits",
     r'''                          r"(?:\.0+)?(?!\.?\d)", low) is not None''',
     r'''                          r"(?:\.0+)?", low) is not None''',
     ["Q24 wrong: ratio 3.00:1.25"]),
    ("a ratio line whose working ends at 3",
     r'''                    if "ratio" in line))''',
     r'''                    if "ratio" in line and False))''',
     ["Q24 ratio line ending at 3.00"]),
    ("a ratio line's 3 does not run on into more digits",
     r'''             or any(re.search(r"=\s*3(?:\.0+)?(?!\.?\d)", line)''',
     r'''             or any(re.search(r"=\s*3(?:\.0+)?", line)''',
     ["Q24 wrong: ratio line ending at 3.125"]),
    ("Q19's direction said beside the figure",
     r'''    return any(re.search(figure, line) and re.search(words, line)''',
     r'''    return False and any(re.search(figure, line) and re.search(words, line)''',
     ["Q19 repeating-decimal currents and comparisons beside "
      "the figure"]),
    ("Q9 reads the failure words",
     r'''              or _FAILURE_STATED.search(low) is not None)''',
     r'''              or False)''',
     ["Q9 next lower rejected as exceeding"]),
    ("'rejected' is a failure word",
     r'''    r"does not meet|violates?|reject(?:s|ed)?)\b")''',
     r'''    r"does not meet|violates?)\b")''',
     ["Q14 next smaller heater rejected"]),
    ("the pass words beside 'pass'",
     r'''    r"pass|\b(?:meets?|satisf(?:ies|y|ied)|"''',
     r'''    r"pass|\b(?:QQQQ|"''',
     ["Q14 the equality pass in the answer's words"]),
    ("'permitted' is a pass word",
     r'''    r"permit(?:s|ted)?|accept(?:s|ed|able)?)\b")''',
     r'''    r"accept(?:s|ed|able)?)\b")''',
     ["Q9 the equality pass in the answer's words"]),
    ("Q4's selection skips the fixed width and length",
     r'''                                    in _Q4_FIXED)):''',
     r'''                                    in ())):''',
     ["Q4 the selection read past the fixed width"]),
    ("Q4's selection reads a sentence, not a line",
     r'''        for sentence in re.split(r"(?<=[.!?])\s+", line):''',
     r'''        for sentence in [line]:''',
     ["Q4 the thickness sentence beside a rejection sentence"]),
    ("a numbered step that runs on into a sentence is no heading",
     r'''    if numbered and re.search(r"[A-Za-z)][.!?](?:\s|$)",''',
     r'''    if False and numbered and re.search(r"[A-Za-z)][.!?](?:\s|$)",''',
     ["Q5 a step that assesses the result is not a results "
      "heading"]),
    ("a compared quantity is a bound",
     r'''            if _COMPARED.search(context.lower()):''',
     r'''            if False and _COMPARED.search(context.lower()):''',
     ["Q5 a compared bound in a results section"]),
    ("a sub-numbered step with no closing mark",
     r'''    r"|\d+(?:\.\d+)+\s"''',
     r'''    r"|QQQQ"''',
     ["Q5 sub-numbered steps with no closing mark"]),
    ("a lettered step label",
     r'''    r"|\**\s*[a-z]\d+\s*[—–:.)-]\s"''',
     r'''    r"|QQQQ"''',
     ["Q20 lettered steps in the answers' own words",
      "Q25 the answers' own forms"]),
    ("Q20: 'adjust' sets the flow",
     r'''_Q20_SETTING = ("set", "adjust")''',
     r'''_Q20_SETTING = ("set",)''',
     ["Q20 lettered steps in the answers' own words"]),
    ("Q20: 'steady' is stabilized",
     r'''_Q20_STEADY = ("stabiliz", "stabilis", "steady")''',
     r'''_Q20_STEADY = ("stabiliz", "stabilis")''',
     ["Q20 lettered steps in the answers' own words"]),
    ("Q20: 'simultaneously' is together",
     r'''_Q20_TOGETHER = ("together", "simultaneous", "at the same instant",''',
     r'''_Q20_TOGETHER = ("together", "QQQQ", "at the same instant",''',
     ["Q20 lettered steps in the answers' own words"]),
    ("Q20: 'divert flow back' is diverting back",
     r'''                    r"re:\bdivert\w*\s+(?:the\s+)?(?:flow\s+)?back")''',
     r'''                    r"re:QQQQ")''',
     ["Q20 lettered steps in the answers' own words"]),
    ("Q20: 'stopping the pump' stops the pump",
     r'''_Q20_PUMP_STOP = ("stop the pump", "stopping the pump",''',
     r'''_Q20_PUMP_STOP = ("stop the pump", "QQQQ",''',
     ["Q20 lettered steps in the answers' own words"]),
    ("Q25: the 0 V start written '0.00 V'",
     r'''        ((r"re:(?<![\d.])0(?:\.0+)?\s*v\b", "zero"),''',
     r'''        ((r"re:(?<![\d.])0\s*v", "zero"),''',
     ["Q25 the answers' own forms"]),
    ("Q25: 'enabling' enables",
     r'''         ("enabl",)),''',
     r'''         ("enable",)),''',
     ["Q25 the answers' own forms"]),
    ("Q25: 'disabling' disables",
     r'''        (("return", _Q25_ZERO_THEN_OFF), ("disabl",)),''',
     r'''        (("return", _Q25_ZERO_THEN_OFF), ("disable",)),''',
     ["Q25 the answers' own forms"]),
    ("Q25: 'Set input to 0.00 V. Then disable' returns to zero",
     r'''        (("return", _Q25_ZERO_THEN_OFF), ("disabl",)),''',
     r'''        (("return",), ("disabl",)),''',
     ["Q25 shutdown: the input set to 0.00 V, then the supply "
      "disabled"]),
    ("Q25: 'increasing' increases",
     r'''              and any(w in low for w in ("increas",''',
     r'''              and any(w in low for w in ("increase",''',
     ["Q25 the answers' own forms"]),
    ("Q25: 'decreasing' decreases",
     r'''               and any(w in low for w in ("decreas",''',
     r'''               and any(w in low for w in ("decrease",''',
     ["Q25 the answers' own forms"]),
    ("Q25: 'LOW→HIGH' is low-to-high",
     r'''_Q25_TO = r"{0}\s*(?:-\s*to\s*-|\s+to\s+|→|->)\s*{1}"''',
     r'''_Q25_TO = r"{0}-to-{1}"''',
     ["Q25 the answers' own forms"]),
    ("Q25: the band written '2.90 V <= V_R <= 3.10 V'",
     r'''             r"|<=\s*[^\n<]{{0,24}}?<=\s*){1}"''',
     r'''             r"|QQQQ){1}"''',
     ["Q25 the answers' own forms"]),
    ("Q25: 'exactly 1' is one transition",
     r'''                      or re.search(r"exactly (?:one|1)\b(?!\.\d)",''',
     r'''                      or re.search(r"QQQQ",''',
     ["Q25 the answers' own forms"]),
    ("Q25: HIGH confirmed at 5.00 V after the record",
     r'''             or (i_record >= 0 and re.search(''',
     r'''             or (False and re.search(''',
     ["Q25 the rise recorded, then HIGH confirmed at 5.00 V"]),
    ("a bare 'C' is degrees Celsius",
     r'''    "c": ("deg C", 1.0),''',
     r'''''',
     ["Q10 temperatures in a bare C"]),
    ("truth-table rows state the outputs",
     r'''        m = _TRUTH_ROW.match(line)''',
     r'''        m = None''',
     ["Q6 outputs as truth-table rows", "Q6 outputs as a mapping"]),
]


def main() -> int:
    source = (TIER2 / "scorer.py").read_text(encoding="utf-8")
    held = 0
    for rule, line, broken, fixtures in BREAKS:
        count = source.count(line)
        if count != 1:
            print(f"NOT APPLIED  {rule}: the line occurs {count} times")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "tier2"
            shutil.copytree(TIER2, copy,
                            ignore=shutil.ignore_patterns("__pycache__"))
            (copy / "scorer.py").write_text(
                source.replace(line, broken), encoding="utf-8")
            out = subprocess.run(
                [sys.executable, "scorer.py", "--self-test"],
                cwd=copy, capture_output=True, text=True).stdout
        failed = {row[len("  FAIL  "):].strip()
                  for row in out.splitlines()
                  if row.startswith("  FAIL  ")}
        missing = [f for f in fixtures if f not in failed]
        if missing:
            print(f"NOT CAUGHT   {rule}: still passing {missing}")
        else:
            held += 1
            print(f"caught       {rule}: {len(failed)} fixture(s) fail, "
                  f"including {fixtures}")
    print(f"\n{held} of {len(BREAKS)} breaks caught by their fixtures")
    return 0 if held == len(BREAKS) else 1


if __name__ == "__main__":
    sys.exit(main())
