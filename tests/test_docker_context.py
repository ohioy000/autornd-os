"""What the Docker build is allowed to copy.

The Dockerfile runs `COPY . .`. Without a `.dockerignore`, a build from a tree
that holds a working `.env` bakes the provider key into the image's
`/app/.env`. Found 2026-11-17 by a cold start from the README, and confirmed
on the machine: an image built from the owner's tree on 2026-11-16 held a
3.4 KB `/app/.env`. After the fix the same tree, with `.env`, `.env.tier3` and
`.env.bak-20261116` in it, built an image holding only `.env.example`.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE = ROOT / ".dockerignore"

# Every spelling an env file has taken in this repository's history, among
# them `.env1` (swept into history once, ARCH-20260930-097) and the dated
# backup the owner's `.env` clean-up leaves.
ENV_FILES = [".env", ".env.tier3", ".env.bak-20261116", ".env1",
             ".env.production", ".env.local"]


def _excluded(name: str) -> bool:
    """Docker's rule for a file at the context root: the last pattern that
    matches decides, and a leading `!` puts the file back in."""
    excluded = False
    for line in IGNORE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        pattern = line[1:] if negate else line
        if fnmatch.fnmatchcase(name, pattern):
            excluded = not negate
    return excluded


class TestTheImageDoesNotCarryTheKey:
    def test_no_env_file_reaches_the_image(self):
        kept = [n for n in ENV_FILES if not _excluded(n)]
        assert kept == [], f"copied into the image by COPY . . : {kept}"

    def test_an_env_file_that_is_in_the_tree_now_is_covered_too(self):
        on_disk = [p.name for p in ROOT.iterdir()
                   if p.name.startswith(".env") and p.name != ".env.example"]
        kept = [n for n in on_disk if not _excluded(n)]
        assert kept == [], f"copied into the image by COPY . . : {kept}"

    def test_the_template_stays_in_the_image(self):
        assert not _excluded(".env.example")

    def test_the_dockerfile_still_copies_the_tree_and_the_ignore_file_exists(self):
        """The ignore file is what the copy relies on; if the copy moved to a
        list of paths this guard would stop meaning anything."""
        assert "COPY . ." in (ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert IGNORE.is_file()
