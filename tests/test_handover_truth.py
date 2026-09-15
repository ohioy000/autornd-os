"""`HANDOVER.md` must not drift from the code again.

**Why this exists.** HANDOVER is the repo's most-read document and was, by
Blueprint 013, its stalest: it described a 16-node flagship that had 21, a
five-node build loop that exited on the validator alone two exits ago, 501
passing tests when there were 651, and the API's own entry point as "legacy" —
a claim that got the module ruled deletable while `api/routes.py` imported it on
every request (convention 19).

Prose is not checkable and a test is. So the numeric claims are **derived from
the source and compared**, not eyeballed, and the claims that were retired by
measurement are guarded against quiet reintroduction.

**On the allowlist.** Several sections exist precisely to record what *used to
be* true — the meter epoch, the live-sequence bug catalogue, the B7 ledger, the
resolved rows of the bug table. Those cite superseded figures on purpose, and a
guard that forbade them would delete the document's memory. They are exempt from
the retired-claims check and never from the derived-count checks, because a
stale *count* is never a historical record of anything.
"""

from __future__ import annotations

import functools
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HANDOVER = Path(__file__).resolve().parents[1] / "HANDOVER.md"
ROOT = HANDOVER.parent


@pytest.fixture(scope="module")
def handover() -> str:
    return HANDOVER.read_text(encoding="utf-8")


@functools.lru_cache(maxsize=1)
def _collected_test_count() -> int:
    """One collection, shared — it is the slowest thing in this file."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True).stdout
    m = re.search(r"(\d+) tests? collected", out)
    if not m:                    # collection itself broke; that is another test's job
        pytest.skip(f"could not collect the suite:\n{out[-400:]}")
    return int(m.group(1))


# ── claims retired by measurement ─────────────────────────────────────────────
#
# Each was asserted in HANDOVER, was measured to be false, and was removed. The
# guard is against writing them again — the document has reacquired a wrong
# claim before, from a diagram nobody re-read.
RETIRED = {
    "The review verdict does not block":
        "review_clean gates on it and routes to the rework loop (§2.3)",
    "is not attributed":
        "research, context and rerank calls are all metered (§6.7)",
    "equivalence reference for the graph":
        "the hardcoded sequencer is gone; the file is the API's entry point",
    "16 nodes": "the flagship has 21",
    "501/501": "the suite is far past this; derive it",
}


def test_retired_claims_are_not_reasserted(handover):
    reasserted = {claim: why for claim, why in RETIRED.items()
                  if claim in handover}
    assert not reasserted, (
        "HANDOVER reasserts claims that measurement retired: "
        + "; ".join(f"{c!r} — {w}" for c, w in reasserted.items()))


# ── counts derived from the source, not from memory ───────────────────────────

def test_node_counts_match_the_workflow_files(handover):
    """Every "<n> nodes" claim about a named workflow must be true."""
    claims = re.findall(r"(\w[\w-]*)\.yaml[^\n|]{0,60}?(\d+) nodes", handover)
    assert claims, "no node-count claims found — did the wording change?"
    wrong = []
    for name, claimed in claims:
        path = ROOT / "workflows" / f"{name}.yaml"
        if not path.exists():
            wrong.append(f"{name}.yaml does not exist")
            continue
        actual = len(yaml.safe_load(path.read_text())["nodes"])
        if int(claimed) != actual:
            wrong.append(f"{name}.yaml: claims {claimed}, has {actual}")
    assert not wrong, "; ".join(wrong)


def test_the_stated_test_total_is_the_real_one(handover):
    """The suite total appears in §3.7 and §7; both must be current."""
    actual = _collected_test_count()
    stated = set(re.findall(r"(\d+) (?:total|tests)[^\n]{0,40}as of `[0-9a-f]{7,}`",
                            handover))
    assert stated, "no commit-stamped test total found in HANDOVER"
    wrong = {n for n in stated if int(n) != actual}
    assert not wrong, (f"HANDOVER states {sorted(wrong)} tests, "
                       f"collection found {actual}")


def test_the_pass_count_is_the_real_one(handover):
    """§4.2 opens with "no failing unit tests — N/N pass"."""
    actual = _collected_test_count()
    m = re.search(r"(\d+)/(\d+) pass", handover)
    assert m, "the §4.2 pass-count line is missing or reworded"
    assert int(m.group(1)) == int(m.group(2)) == actual, (
        f"§4.2 claims {m.group(0)}, collection found {actual}")


def test_every_test_file_count_is_right(handover):
    """"N test files" / "N files, M tests" must match what is on disk.

    Checked in `AGENTS.md` too, because the protocol file carries the same
    count and a protocol file that is wrong about the repo is the worst place
    for a stale number to sit.
    """
    actual = len(list((ROOT / "tests").glob("test_*.py")))
    sources = {"HANDOVER.md": handover,
               "AGENTS.md": (ROOT / "AGENTS.md").read_text(encoding="utf-8")}
    for name, text in sources.items():
        claims = [int(n) for n in re.findall(r"(\d+) (?:test )?files", text)]
        assert claims, f"no test-file count found in {name}"
        assert all(n == actual for n in claims), (
            f"{name} claims {sorted(set(claims))} test files, disk has {actual}")


def test_named_checks_exist(handover):
    """§2.3 lists the free checks by name; the registry is the truth."""
    from autornd.graph.checks import registry

    listed = set(re.findall(r"`(criteria_addressed|numbers_consistent|"
                            r"totals_reconcile|judges_agree)`", handover))
    missing = listed - set(registry)
    assert not missing, f"HANDOVER names checks that do not exist: {missing}"


def test_the_workflow_facade_is_still_described_as_on_the_request_path(handover):
    """Convention 19's whole point. If this line goes, the module is deletable
    again by the same reasoning that nearly deleted it before."""
    assert "engine/workflow.py" in handover or "WorkflowEngine" in handover
    assert "request path" in handover, (
        "HANDOVER no longer says WorkflowEngine is on the request path — "
        "that omission is what got it ruled legacy (convention 19)")
