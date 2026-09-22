"""B20: a paid run's records must survive the directory entry going away.

**The measurement.** On 2026-09-22 a live run was writing
`docs/traces/b17-validation-marketing-claims-grounded.jsonl` when `git stash -u`
took the file. The writer held the inode; the directory entry was gone; every
flushed unit record went to an unlinked file and died when the handle closed.
**$0.1547, unrecoverable, one 729-byte header surviving.**

**Two things the record got wrong before this repair, both corrected here.**

*Flushing was never the problem.* `ResultsLog._write` has flushed per record
since it was written, and the docstring says so. Flushing does not help once the
directory entry is gone — that is the whole mechanism.

*Ignoring `docs/traces/` is not the fix.* It is **tracked**, 60 committed files,
and it is the evidence model: traces are committed on purpose. Ignoring it would
stop that. The default results path `evals/results/` **is** already ignored and
was never exposed — `git stash -u` takes untracked files, not ignored ones. The
loss happened because `--results-file` aimed at the one directory that is
tracked, where a brand-new file is untracked until it is committed.

So the repair is a mirror **outside the working tree**, not a change to where
the evidence lives.

**What this does not protect against, stated rather than implied:** `git stash
-a` (which takes ignored files too, though not the mirror — that is outside the
repo entirely), deletion of the state directory, filesystem loss, and a `kill
-9` between two records. It closes one mechanism, the one that actually fired.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from autornd.evals.runner import ResultsLog, _durable_mirror


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "state"


class TestTheMirrorIsChosenByHazardNotByHabit:
    def test_a_tracked_in_repo_path_is_mirrored(self, state_dir):
        assert _durable_mirror(Path("docs/traces/x.jsonl")) is not None

    def test_an_already_ignored_path_is_not_mirrored(self, state_dir):
        """`evals/results/` is git-ignored, so `stash -u` never reached it.
        Mirroring it would be storage spent on a hazard that does not exist."""
        assert _durable_mirror(Path("evals/results/x.jsonl")) is None

    def test_a_path_outside_any_working_tree_is_not_mirrored(self, state_dir):
        assert _durable_mirror(Path("/tmp/x.jsonl")) is None

    def test_the_mirror_is_outside_the_repository(self, state_dir):
        mirror = _durable_mirror(Path("docs/traces/x.jsonl"))
        repo = Path.cwd().resolve()
        assert repo not in mirror.resolve().parents
        assert mirror.resolve() != repo


class TestTheRecordsSurviveTheDirectoryEntryGoingAway:
    """The actual loss, reproduced: unlink the file mid-write and keep going,
    exactly as `git stash -u` did."""

    def test_completed_units_survive_an_unlink_mid_run(self, state_dir):
        primary = Path("docs/traces/_durability_probe.jsonl")
        log = ResultsLog(primary, config={"suite": "probe"})
        try:
            log._write({"record": "unit", "repetition": 1, "cost": 0.05})

            # This is `git stash -u`. The handle stays open and valid; the name
            # stops pointing at it.
            primary.unlink()
            assert not primary.exists()

            # The run carries on, as it did, and pays for more work.
            log._write({"record": "unit", "repetition": 2, "cost": 0.06})
        finally:
            log.close()

        assert not primary.exists(), "the primary is gone, as it was"

        records = [json.loads(line) for line in
                   log.mirror_path.read_text().splitlines() if line.strip()]
        kinds = [r["record"] for r in records]
        assert kinds == ["header", "unit", "unit"], (
            f"the mirror lost records the run paid for: {kinds}")
        assert [r["repetition"] for r in records if r["record"] == "unit"] == [1, 2]

    def test_the_primary_is_still_written_when_nothing_disturbs_it(self, state_dir):
        """The mirror must not become the only copy. Traces are committed from
        the primary path and that has to keep working."""
        primary = Path("docs/traces/_durability_probe2.jsonl")
        try:
            with ResultsLog(primary, config={"suite": "probe"}) as log:
                log._write({"record": "unit", "repetition": 1})
            lines = [json.loads(x) for x in
                     primary.read_text().splitlines() if x.strip()]
            assert [r["record"] for r in lines] == ["header", "unit"]
        finally:
            primary.unlink(missing_ok=True)


class TestTheOperatorIsTold:
    """A protection nobody knows about is a protection nobody uses — and a
    silent mirror is an instrument asserting durability it never mentioned
    (convention 28)."""

    def test_the_cli_names_the_mirror(self, state_dir, capsys):
        from autornd.evals.cli import ResultsLog as CliResultsLog  # same class

        primary = Path("docs/traces/_durability_probe3.jsonl")
        try:
            log = CliResultsLog(primary, config={})
            log.close()
            assert log.mirror_path is not None
            assert "autornd" in str(log.mirror_path)
        finally:
            primary.unlink(missing_ok=True)
