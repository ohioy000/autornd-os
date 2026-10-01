"""No env-named file but the template can be staged (ARCH-20260930-097).

**What bought this.** During 093, commit 1f7823e swept `.env1`, an untracked
file holding an old provider key, into history, and GitHub secret scanning
blocked the push. `.gitignore` named exactly `.env`, so `git add -A` staged
every other env-named file. No paid run was involved, so the preflight gate
(096) could not have stopped it.

**What these tests read.** Ignore rules and tracked paths only. They never
open, list or stat an env file (G-1): `git check-ignore --no-index` judges a
path name against the rules whether or not the file exists, and `--no-index`
matters. Without it, git reports a tracked path as not ignored whatever the
rules say, so the `.env.example` probe would pass even with its exception
deleted.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _ignored(name: str) -> bool:
    proc = subprocess.run(["git", "check-ignore", "--no-index", "-q", name],
                          cwd=ROOT, capture_output=True, text=True)
    # 0 ignored, 1 not ignored. Anything else means git did not answer, which
    # is no evidence, never a pass (convention 28).
    assert proc.returncode in (0, 1), f"git check-ignore failed: {proc.stderr}"
    return proc.returncode == 0


class TestEveryEnvNameIsIgnored:
    """(a) Each probe asserted on its own, so one cannot hide another."""

    @pytest.mark.parametrize("name", [".env", ".env1", ".env.bak", ".env.local"])
    def test_an_env_named_file_is_ignored(self, name):
        assert _ignored(name), f"{name} could be staged by git add"

    def test_the_template_is_not_ignored(self):
        assert not _ignored(".env.example")


class TestNoEnvFileIsTracked:
    """(b) The rule stops new files; this catches one already in the index."""

    def test_the_template_is_the_only_tracked_env_name(self):
        proc = subprocess.run(["git", "ls-files"], cwd=ROOT,
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        paths = proc.stdout.splitlines()
        assert len(paths) > 100, "git ls-files listed almost nothing: no evidence"
        # Any depth, by basename: a nested .env would leak just the same.
        env_named = [p for p in paths if re.match(r"\.env", p.rsplit("/", 1)[-1])]
        assert env_named == [".env.example"], env_named
