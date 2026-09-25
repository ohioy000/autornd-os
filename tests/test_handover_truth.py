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
    """The suite total appears in §3.7 and §7; both must be current.

    Historical figures inside quoted past-tense exhibit text (the B22 row
    quoting its own 2026-09-22 header) are the document's memory, not claims
    about this tree — the module docstring's allowlist principle. Only stamps
    OUTSIDE backtick-quoted exhibit spans count.
    """
    actual = _collected_test_count()
    unquoted = re.sub(r"``[^`]*``", "", handover)
    stated = set(re.findall(r"(\d+) (?:total|tests)[^\n]{0,40}as of `[0-9a-f]{7,}`",
                            unquoted))
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


# ── the provenance stamp ──────────────────────────────────────────────────
#
# ARCH-20260922-014. HANDOVER's header names a sha twice — the snapshot's HEAD
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
# The property the stamp is meant to have is the one `f5b5810` acted on when it
# named `4bfbbc5` rather than its own sha: the stamp names a real commit that is
# an ANCESTOR of the one under test. Resolvable is weaker and would pass a sha
# from an abandoned branch.

# The markdown between the label and the sha is part of the document, not
# noise: the header reads "**HEAD:** `039cabe`" and "**Tests:** 808 as of
# `a2e362e`". A first version of this pattern used `\s*` after the label,
# matched NOTHING, and passed all three break attempts — a guard that could not
# fail, written inside the change that exists to stop guards that cannot fail.
# `_STAMP` is therefore asserted to find something before anything is checked.
# Every stamp guard says this, because on 2026-09-22 only ONE of the three got
# the non-empty assertion and the other two went on passing vacuously for
# another hour. A fix applied to the instance you are looking at is not a fix
# applied to the class.
_NOTHING_FOUND = (
    "the stamp pattern matched nothing, so every check below this line would "
    "iterate an empty list and pass. That is not a clean bill (convention 28)."
)

_STAMP = re.compile(r"(?:HEAD:|as of)[^`\n]{0,24}`([0-9a-zA-Z]{6,40})`")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(("git",) + args, cwd=ROOT,
                          capture_output=True, text=True)


def _shallow() -> bool:
    return _git("rev-parse", "--is-shallow-repository").stdout.strip() == "true"


def test_the_provenance_stamps_are_not_placeholders(handover):
    """`PENDINGSHA` shipped once and was replaced by hand."""
    stamps = _STAMP.findall(handover)
    assert len(stamps) >= 2, (
        f"HANDOVER should carry a HEAD stamp and a test-count stamp; the "
        f"pattern found {stamps}. A pattern that matches nothing makes every "
        f"check below vacuous, which is how the first version of this guard "
        f"passed all three break attempts.")
    bad = [s for s in stamps if not re.fullmatch(r"[0-9a-f]{7,40}", s)]
    assert not bad, (
        f"HANDOVER's provenance stamp is not a sha: {bad}. "
        "PENDINGSHA shipped once already (4bfbbc5).")


def test_the_provenance_stamps_resolve_to_real_commits(handover):
    """`cafebabe` was hand-typed and looked exactly like a sha."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    stamps = _STAMP.findall(handover)
    assert stamps, _NOTHING_FOUND
    unresolved = [s for s in stamps
                  if _git("cat-file", "-t", s).stdout.strip() != "commit"]
    assert not unresolved, (
        f"HANDOVER names shas that are not commits in this repo: {unresolved}")


def test_the_provenance_stamps_are_ancestors_of_the_commit_under_test(handover):
    """The property that `resolvable` misses: a sha from an abandoned branch
    resolves perfectly well and describes a state this commit never passed
    through."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    if _shallow():
        pytest.skip(
            "shallow clone — ancestry is unanswerable at fetch-depth 1. "
            "test_ci_gives_one_job_the_history_this_guard_needs keeps this "
            "skip from becoming permanent.")
    stamps = _STAMP.findall(handover)
    assert stamps, _NOTHING_FOUND
    strangers = [s for s in stamps
                 if _git("merge-base", "--is-ancestor", s, "HEAD").returncode != 0]
    assert not strangers, (
        f"HANDOVER names shas that are not ancestors of HEAD: {strangers}. "
        "A stamp naming a commit this one never descended from records a state "
        "the repo was never in.")


def test_ci_gives_one_job_the_history_this_guard_needs():
    """A guard that skips in CI forever is a guard that cannot fail, which is
    the whole class of defect this repo keeps finding. The ancestry check above
    skips on a shallow clone by necessity; this pins the CI config that stops
    the skip being permanent."""
    import yaml

    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    depths = [
        step.get("with", {}).get("fetch-depth")
        for job in ci["jobs"].values()
        for step in job.get("steps", [])
        if str(step.get("uses", "")).startswith("actions/checkout")
    ]
    assert 0 in depths, (
        "No CI job checks out full history, so the provenance-stamp ancestry "
        "guard skips on every run. Set fetch-depth: 0 on the job that runs "
        "pytest.")


# How far the document's own stamp may lag the commit under test, counted in
# commits that actually MODIFIED HANDOVER.md.
#
# It cannot be zero: the commit that writes the stamp necessarily edits the
# document, so a freshly-stamped document always lags itself by one. Three
# allows that commit, a merge commit, and one concurrent edit landing beside it.
#
# It is not a finely-tuned number. Measured 2026-09-22 (B22): the stamp read
# `039cabe` while 32 HANDOVER-touching commits had landed since, and its
# companion tests stamp read `8bb0cbc` with 9. The gap between 3 and 32 is an
# order of magnitude, so the bound distinguishes "just stamped" from "a day
# stale" without needing to be exact.
_MAX_STAMP_LAG = 3


# ── Ruling D18: the stamp must name main and an ancestor of main ──────────
#
# ARCH-20260925-058. At main `01632c9` the HANDOVER header named commit
# `2e75232` on branch `arch/20260923-053-actionable-terminal` — a branch that
# no longer existed. Resolvability and ancestry-of-HEAD both passed on it:
# the commit resolved, and HEAD moves with every branch, so on the -053
# branch itself the stamp was a genuine ancestor. The defect was that the
# stamp pointed somewhere main had never been. A stamp must therefore name
# (a) a branch that EXISTS, and (b) a commit that is an ancestor of MAIN
# specifically — not of whatever HEAD happens to be checked out. The existing
# guards keep their jobs: placeholders, resolvability, ancestry-of-HEAD,
# coherence, freshness. These three are additive.
#
# Each of the three is proved by breaking it below the test (convention 22):
# a fabricated branch, a real commit from a side branch, and a wrong count.
# The break-quotes are recorded in docs/handover-review.md §66 alongside the
# run that produced them.


def _header_branch_and_sha(handover: str) -> tuple[str, str]:
    """The branch and sha the header stamp names.

    Returns (branch, sha). Asserts the subject before asserting anything
    about it (convention 28): a stamp the pattern cannot find is no evidence,
    and no evidence must never read as no problem.
    """
    branch = re.search(r"\*\*Branch:\*\*\s*`([^`]+)`", handover)
    sha = re.search(r"HEAD:[^`\n]{0,24}`([0-9a-f]{7,40})`", handover)
    assert branch and sha, _NOTHING_FOUND
    return branch.group(1), sha.group(1)


def test_the_stamp_names_a_branch_that_exists(handover):
    """D18(a): the named branch must exist — locally or on the remote."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    named_branch, _ = _header_branch_and_sha(handover)
    local = _git("show-ref", "--verify", f"refs/heads/{named_branch}")
    remote = _git("show-ref", "--verify", f"refs/remotes/origin/{named_branch}")
    assert local.returncode == 0 or remote.returncode == 0, (
        f"HANDOVER's Branch stamp `{named_branch}` names a branch that does "
        f"not exist locally or on origin. The stamp at main `01632c9` named "
        f"`arch/20260923-053-actionable-terminal`, deleted at merge — a "
        f"stamp pointing at a deleted branch is not a stamp (Ruling D18).")


def test_the_stamp_names_an_ancestor_of_main(handover):
    """D18(b): the named commit must be an ancestor of MAIN, not of HEAD.

    HEAD moves with every checkout, so ancestry-of-HEAD passes on any branch
    that contains the stamp. Main is the state of record (D15); a stamp must
    name somewhere main has been.
    """
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    if _shallow():
        pytest.skip("shallow clone — ancestry is unanswerable at fetch-depth 1")
    _, named_sha = _header_branch_and_sha(handover)
    main = _git("rev-parse", "main")
    assert main.returncode == 0, "no local main — cannot check main-ancestry"
    is_ancestor = _git("merge-base", "--is-ancestor", named_sha, "main")
    assert is_ancestor.returncode == 0, (
        f"HANDOVER's HEAD stamp `{named_sha}` is not an ancestor of main "
        f"(`{main.stdout.strip()[:7]}`). Resolvable and ancestor-of-HEAD both "
        f"pass on a stamp from a live side branch; only main-ancestry catches "
        f"it (Ruling D18, third exhibit of B22).")


def test_the_stamped_count_matches_the_collected_suite(handover):
    """D18(c): the stamped count must equal the suite's collected count.

    The total-guard checks every `N … as of <sha>` line; this checks the one
    in the header specifically, so a header that drifts while §3.7 stays
    current still fails. One collection, shared with the total guard.
    """
    header_count = re.search(r"\*\*Tests:\*\*\s*(\d+)\s+as of", handover)
    assert header_count, _NOTHING_FOUND
    actual = _collected_test_count()
    assert int(header_count.group(1)) == actual, (
        f"HANDOVER's header stamps {header_count.group(1)} tests, collection "
        f"found {actual} (Ruling D18).")


def _break_d18a_nonexistent_branch(handover: str) -> str:
    """Prove D18(a) by breaking it: stamp a branch that never existed."""
    return re.sub(r"\*\*Branch:\*\*\s*`[^`]+`",
                  "**Branch:** `branch-that-never-existed`", handover, count=1)


def _break_d18b_side_branch_commit(handover: str) -> str:
    """Prove D18(b) by breaking it: stamp a real commit main never passed.

    Demonstrated against a SYNTHETIC main: the break swaps the `main` the
    guard checks for a ref that does not contain the stamped commit, so the
    ancestry test runs its real `merge-base` path and fails. A live
    side-branch tip cannot serve — every local branch tip is already merged
    to main (checked 2026-09-25: all eight `arch/*` tips return exit 0
    against main), and a fabricated sha fails resolvability first, proving
    the wrong guard. The synthetic-main failure exercises exactly the
    `merge-base --is-ancestor <sha> main` path the guard depends on, with a
    subject that resolves (convention 28: the guard computed before judging).
    """
    return re.sub(r"HEAD:[^`\n]{0,24}`[0-9a-f]{7,40}`",
                  "HEAD:** `2e75232`", handover, count=1)


def _main_without_history() -> str:
    """A ref main never passed: the root commit's tree with no parents.

    `git hash-object -t commit` writes no object; `commit-tree` with no
    parents creates a real, resolvable commit sharing nothing with main's
    history. The stamped `2e75232` resolves (so resolvability passes) and is
    an ancestor of the checkout's HEAD (so ancestry-of-HEAD passes), but is
    not an ancestor of this synthetic main — the exact shape D18(b) exists
    to catch. Caller must delete the ref afterwards; see the test.
    """
    empty_tree = _git("hash-object", "-t", "tree", "/dev/null").stdout.strip()
    return _git("commit-tree", empty_tree,
                "-m", "synthetic main for D18(b) demonstration").stdout.strip()


def _break_d18c_wrong_count(handover: str) -> str:
    """Prove D18(c) by breaking it: stamp a count one off the suite."""
    actual = _collected_test_count()
    return re.sub(r"\*\*Tests:\*\*\s*\d+\s+as of",
                  f"**Tests:** {actual + 1} as of", handover, count=1)


class TestD18GuardsProveThemselves:
    """Each D18 guard fails on its broken input with the message quoted.

    The break is applied to the live document text, so the demonstration runs
    against the stamp as stamped — not against a fixture that can drift from
    it. Quoted messages are recorded in the notebook (§66) beside the run.
    """

    def test_a_nonexistent_branch_fails_loudly(self, handover):
        broken = _break_d18a_nonexistent_branch(handover)
        with pytest.raises(AssertionError, match="does not exist"):
            test_the_stamp_names_a_branch_that_exists(broken)

    def test_a_side_branch_commit_fails_loudly(self, handover):
        broken = _break_d18b_side_branch_commit(handover)
        synthetic = _main_without_history()
        _git("update-ref", "refs/heads/__d18_synthetic_main", synthetic)
        real_main = _git("rev-parse", "main").stdout.strip()
        try:
            _git("update-ref", "refs/heads/main",
                 "__d18_synthetic_main")
            with pytest.raises(AssertionError,
                               match="not an ancestor of main"):
                test_the_stamp_names_an_ancestor_of_main(broken)
        finally:
            _git("update-ref", "refs/heads/main", real_main)
            _git("update-ref", "-d", "refs/heads/__d18_synthetic_main")

    def test_a_wrong_count_fails_loudly(self, handover):
        broken = _break_d18c_wrong_count(handover)
        with pytest.raises(AssertionError, match="collection"):
            test_the_stamped_count_matches_the_collected_suite(broken)


def test_the_head_stamp_is_the_newest_sha_the_document_stamps(handover):
    """Internal coherence: HEAD cannot be older than a fact the document reports.

    **The defect this exists for (B22).** The header read ``**HEAD:** `039cabe` ``
    beside ``**Tests:** 931 as of `8bb0cbc` `` — and `039cabe` is an ANCESTOR of
    `8bb0cbc`. The document claimed to describe a commit older than the commit
    whose test count it was reporting. Both stamps resolved, both were ancestors
    of HEAD, and all three existing guards passed.

    HEAD names the commit the document DESCRIBES. That reading is forced by the
    header's own shape: the snapshot DATE is carried separately, so HEAD would
    be redundant if it meant "last substantive rewrite", and the tests stamp
    carries its own sha, so HEAD is the document-level equivalent of a per-fact
    stamp. A description cannot predate what it describes.
    """
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    if _shallow():
        pytest.skip("shallow clone — ancestry is unanswerable at fetch-depth 1")

    head = re.search(r"HEAD:[^`\n]{0,24}`([0-9a-f]{7,40})`", handover)
    assert head, _NOTHING_FOUND
    head_sha = head.group(1)

    # Non-vacuity is about the PATTERN finding stamps, not about the shas
    # differing. A correctly maintained document stamps every fact at the same
    # commit, so "all stamps equal" is the right answer and must not be
    # mistaken for "nothing to check" — an earlier version of this assertion
    # required a differing sha and therefore failed on exactly the state it
    # exists to certify.
    stamps = _STAMP.findall(handover)
    assert len(stamps) >= 2, _NOTHING_FOUND
    others = [s for s in stamps if s != head_sha]

    newer = [s for s in others
             if _git("merge-base", "--is-ancestor", head_sha, s).returncode == 0
             and _git("rev-parse", s).stdout != _git("rev-parse", head_sha).stdout]
    assert not newer, (
        f"HANDOVER's HEAD stamp `{head_sha}` is OLDER than shas it stamps "
        f"elsewhere: {newer}. A document whose HEAD predates its own newest "
        f"stamp describes a state that never existed.")


def test_the_head_stamp_is_fresh_not_merely_a_real_ancestor(handover):
    """The property `resolvable` and `ancestor` both miss: staleness.

    A stamp a month old resolves and is an ancestor. Both existing guards pass
    on it, which is exactly what happened — `039cabe` sat in the header while
    32 commits edited the document underneath it.

    **What this measures, and nothing more** (convention 26): the number of
    commits that modified HANDOVER.md between the stamped sha and the commit
    under test. It does NOT establish that the stamp is correct, only that the
    document has not been substantially rewritten since it was written. A set
    of stamps that are uniformly and consistently stale would still pass, and
    `test_the_head_stamp_is_the_newest_sha_the_document_stamps` is what covers
    the incoherent case.
    """
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    if _shallow():
        pytest.skip("shallow clone — rev-list is unanswerable at fetch-depth 1")

    head = re.search(r"HEAD:[^`\n]{0,24}`([0-9a-f]{7,40})`", handover)
    assert head, _NOTHING_FOUND
    head_sha = head.group(1)

    counted = _git("rev-list", "--count", f"{head_sha}..HEAD", "--", "HANDOVER.md")
    assert counted.returncode == 0, (
        f"could not count commits between `{head_sha}` and HEAD: "
        f"{counted.stderr.strip()}. An uncountable lag is no evidence, and no "
        f"evidence must not read as no problem (convention 28).")
    lag = int(counted.stdout.strip() or 0)

    assert lag <= _MAX_STAMP_LAG, (
        f"HANDOVER's HEAD stamp `{head_sha}` is STALE: {lag} commits have "
        f"modified HANDOVER.md since it, against a bound of {_MAX_STAMP_LAG}. "
        f"The stamp resolves and is an ancestor, so the other guards pass — "
        f"staleness is the property they miss (B22). Restamp to the commit "
        f"this change is built on.")
