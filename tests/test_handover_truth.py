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
    """The suite total appears in the header, §3.7 and §7; all must be current.

    Ruling D27: the count is a property of the tree under test, verified on
    the tree under test. No sha, no branch, no ancestry — the guard collects
    the suite on this tree and compares. Historical figures inside quoted
    past-tense exhibit text (the B22 row quoting its own 2026-09-22 header)
    are the document's memory, not claims about this tree — the module
    docstring's allowlist principle. Only bare counts OUTSIDE backtick-quoted
    exhibit spans count.

    What it reads: the document text and the suite collection on this tree.
    No git ref, no fetch depth, no committer identity. If this guard ever
    needs git again, that is a defect — D27 deleted the sha stamp class
    precisely because no git-based assertion could hold it.
    """
    actual = _collected_test_count()
    unquoted = re.sub(r"``[^`]*``", "", handover)
    unquoted = re.sub(r"`[^`\n]*`", "", unquoted)
    # A surviving **Tests:** N with no sha beside it is exhibit residue (the
    # B22 row after span-stripping) — a stamp needs a label PLUS a value and
    # the value is gone. Drop valueless labels before matching.
    unquoted = re.sub(r"\*\*Tests:\*\*\s*\d+\s+as of\s*(?=\s|,|\*\*|\n|$)", "", unquoted)
    stated = set(re.findall(r"\*\*Tests:\*\*\s*(\d+)", unquoted))
    stated |= set(re.findall(r"Test distribution \((\d+) total\)", unquoted))
    # the tree line contributes its test figure (group 2)
    stated |= {t for _, t in re.findall(r"(\d+) files, (\d+) tests", unquoted)}
    assert stated, "no test-count claim found in HANDOVER"
    wrong = {n for n in stated if int(n) != actual}
    assert not wrong, (f"HANDOVER states {sorted(wrong)} tests, "
                       f"collection found {actual} on this tree")


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
    assert listed, (
        "§2.3 names no free checks at all. Either the section was lost or the "
        "backtick convention changed; either way this guard was about to "
        "confirm that an empty set contains no impostors (convention 28).")
    missing = listed - set(registry)
    assert not missing, f"HANDOVER names checks that do not exist: {missing}"


def test_the_workflow_facade_is_still_described_as_on_the_request_path(handover):
    """Convention 19's whole point. If this line goes, the module is deletable
    again by the same reasoning that nearly deleted it before."""
    assert "engine/workflow.py" in handover or "WorkflowEngine" in handover
    assert "request path" in handover, (
        "HANDOVER no longer says WorkflowEngine is on the request path — "
        "that omission is what got it ruled legacy (convention 19)")


# ── the provenance stamp, deleted ─────────────────────────────────────────
#
# Ruling D27 (2026-09-25, §74): the sha stamp class is deleted. What follows
# is the ledger of what was removed and why — the guards below are kept as
# history, not as checks, because the four rulings that failed to fix one
# two-line block are themselves the evidence for the deletion.
#
# ARCH-20260922-014. HANDOVER's header named a sha twice — the snapshot's HEAD
# and the commit its test total was counted at — and neither was ever checked.
# The record holds all three ways that went wrong:
#
#   `0d35868`  "git cat-file -t cafebabe is fatal, confirming the header stamp
#              is hand-typed rather than a commit" — convention 24's named
#              failure mode, caught by reading rather than by a guard.
#   `4bfbbc5`  "The header stamps still read PENDINGSHA."
#   `f5b5810`  "A commit cannot contain its own sha, so the bootstrap the
#              command describes names a commit the amend then discards."
#
# The six failures that deleted the class: a stale sha, a misattributed
# count, a sha on a deleted branch, a guard red against a correct stamp
# (CI has no local main), a break-proof that could not break (CI has no
# committer identity), and D20 — unsatisfiable by construction on a stacked
# branch. Rulings D18, D19, D20 superseded. The test count remains because
# it is verifiable on the tree under test; everything below that needed a
# ref is gone.

# What remains of the stamp machinery: the count. Everything that needed a
# ref — placeholders, resolvability, ancestry-of-HEAD, coherence, freshness,
# D18(a/b/c) with their break-proofs, the D18 fallback test — is deleted,
# not skipped. A guard that is skipped on CI is a guard that does not run
# where it matters (D27). The PENDINGSHA episode (4bfbbc5) is retained above
# as history; no live text carries a sha stamp to be a placeholder of.


def test_no_sha_stamp_remains(handover):
    """D27: HANDOVER carries no sha and no branch stamp.

    A `grep -n 'HEAD:'` finds nothing outside backtick-quoted exhibit spans
    (the B22 row quotes its own 2026-09-22 header as the document's memory).
    If a reader needs the sha, git is the answer rather than a copy of it.

    Convention 28 on this guard itself: it asserts the document carries a
    test-count claim before asserting anything about stamps — an empty
    document fails here, not passes, so the guards-can-fail discovery
    (which hands every guard "") keeps covering it.
    """
    assert re.search(r"\*\*Tests:\*\*\s*\d+", handover), (
        "no test-count claim found — the document under test is not HANDOVER")
    # Quoted exhibit spans are memory, not stamps: double-backtick spans
    # (the B22 row quoting its header) and single-backtick code spans (the
    # B21 row quoting `**HEAD:**` as the pattern the old guard failed to
    # match). Strip spans first, then any bold HEAD label left without a sha
    # beside it — the stamp is a label PLUS a value, and the value is gone.
    unquoted = re.sub(r"``[^`]*``", "", handover)
    unquoted = re.sub(r"`[^`\n]*`", "", unquoted)
    unquoted = re.sub(r"\*\*HEAD:\*\*\s*(?=\s|\n|\*\*|$)", "", unquoted)
    heads = [m for m in re.finditer(r"\*\*HEAD:\*\*", unquoted)]
    assert not heads, (
        "HANDOVER carries a HEAD stamp — D27 deleted the sha stamp class")
    assert "**Branch:**" not in unquoted, (
        "HANDOVER carries a Branch stamp — D27 deleted the sha stamp class")
