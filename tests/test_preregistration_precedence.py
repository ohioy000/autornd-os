"""A pre-registration's only claim is that it came first. Nothing checked it.

**Why this exists.** On 2026-09-22 the B17-R1 validation's pre-registration was
authored at `05:57:12Z` and the run's trace header written at `05:57:26Z` —
fourteen seconds, and the registration provably preceded the run. That was
established by comparing a commit's author date to a JSON field **by hand**,
after the fact, by someone who thought to look.

The protocol's entire value rests on that ordering: *"Pre-register before a paid
run, and commit it first. The commit is the evidence that the prediction
preceded the result."* A claim that load-bearing and that cheap to check should
not depend on anyone thinking to look. Convention 28 pointed at the protocol
itself.

**Author dates, not committer dates.** A rebase rewrites the committer date and
leaves the author date alone, and this repository rebases constantly. Using the
committer date would make every rebase look like a registration written after
its own run.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TRACES = ROOT / "docs" / "traces"

# A pre-registration and the trace it registered, paired by hand because the
# filenames do not encode the link. Adding a pair is the cost of registering a
# run, and it is a smaller cost than an unverifiable claim.
REGISTERED = [
    ("docs/preregistration-b17-validation.md",
     "docs/traces/b17-validation-marketing-claims-grounded.jsonl"),
    ("docs/preregistration-b14-demonstration.md",
     "docs/traces/b14-demo-marketing-claims-grounded.jsonl"),
    # Found by test_every_committed_preregistration_is_paired_or_unrun on the
    # day it was written: B016's closing evidence, a paid run whose precedence
    # nobody had ever checked, three ledger rows later.
    ("docs/preregistration-b016-part-e.md",
     "docs/traces/b16-e1-marketing-claims.jsonl"),
    ("docs/preregistration-b14-rerun-2.md",
     "docs/traces/b14-rerun-2-marketing-claims.jsonl"),
    ("docs/preregistration-049-live-terminal.md",
     "docs/traces/049-live-terminal.jsonl"),
]


def _first_authored(path: str) -> datetime | None:
    """When the file was first committed, by AUTHOR date — rebase-proof."""
    out = subprocess.run(
        ["git", "log", "--follow", "--diff-filter=A", "--format=%aI", "--", path],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip().splitlines()
    return datetime.fromisoformat(out[-1]) if out else None


def _trace_written(path: str) -> datetime | None:
    full = ROOT / path
    if not full.exists():
        return None
    with full.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            written = json.loads(line).get("written_at")
            return datetime.fromisoformat(written) if written else None
    return None


def test_there_are_registered_pairs_to_check():
    """Convention 28. An empty REGISTERED list would make every case below
    vanish and this file pass while checking nothing."""
    assert REGISTERED, "no pre-registration/trace pairs are registered"


@pytest.mark.parametrize("prereg,trace", REGISTERED, ids=lambda v: Path(v).stem)
def test_the_registration_preceded_the_run(prereg, trace):
    if not (ROOT / ROOT.name).exists() and not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")

    authored = _first_authored(prereg)
    written = _trace_written(trace)

    assert authored is not None, (
        f"{prereg} has no commit adding it — the precedence claim rests on "
        f"that commit and there isn't one")
    assert written is not None, (
        f"{trace} carries no written_at header, so nothing can be compared "
        f"against it. An unverifiable claim is not a weaker claim; it is a "
        f"different one (convention 28)")

    assert authored <= written.astimezone(timezone.utc), (
        f"{Path(prereg).name} was authored {authored.isoformat()} but "
        f"{Path(trace).name} was written {written.isoformat()} — the "
        f"registration did NOT precede the run, which is the only thing a "
        f"pre-registration asserts")


def test_every_committed_preregistration_is_paired_or_unrun():
    """A pre-registration with a trace nobody paired is a precedence claim
    nobody checks. Unrun registrations are fine and are the normal state before
    a run; a registration whose run HAS happened must be listed above."""
    paired = {p for p, _ in REGISTERED}
    on_disk = sorted(str(p.relative_to(ROOT))
                     for p in (ROOT / "docs").glob("preregistration-*.md"))
    assert on_disk, "no pre-registrations found — did the naming change?"

    unpaired = [p for p in on_disk if p not in paired]
    # Each unpaired file must have no trace that obviously belongs to it.
    orphaned = []
    for prereg in unpaired:
        text = (ROOT / prereg).read_text(encoding="utf-8")
        for ref in re.findall(r"docs/traces/([\w.\-]+\.jsonl)", text):
            if (TRACES / ref).exists():
                orphaned.append(f"{prereg} -> docs/traces/{ref}")
    assert not orphaned, (
        "these pre-registrations name a trace that exists, so their runs "
        "happened, but no precedence pair is registered for them: "
        + "; ".join(sorted(set(orphaned))))
