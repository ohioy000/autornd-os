"""Every committed doc manifest resolves, and the studio corpus is non-engineering.

**Why the second half matters.** B14 gave the two structural role slots to the
profile, and it is closed as *implemented and guarded* rather than
*demonstrated* — because until now there was no non-engineering corpus to
demonstrate it against. `docs/smartfactory/` looked like one and is not: its
manifest's domains are `firmware`, `hardware`, `backend`, `frontend`,
`infrastructure` — **five shipped `Domain` enum members**. It would run on the
engineering path untouched (`ARCH-20260920-009`).

So `docs/meridian_studio/` exists, and this pins the property that makes it
useful: **not one of its domains is a shipped enum member.** If that ever stops
being true the corpus has drifted back toward engineering and stops validating
anything.

The first half is ordinary rot protection: a manifest naming a file that does
not exist fails silently at run time — `_read_doc` logs a warning and returns
None — so the grounding a run was promised simply does not arrive.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autornd.models.verdicts import Domain, domain_key

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MANIFESTS = sorted(DOCS.glob("*/manifest.json")) + [DOCS / "manifest.json"]
SHIPPED_DOMAINS = {domain_key(d) for d in Domain}


def _paths(manifest: dict) -> set[str]:
    out = set(manifest.get("global", []) or [])
    for paths in (manifest.get("domains") or {}).values():
        out |= set(paths or [])
    for paths in (manifest.get("specialist_extras") or {}).values():
        out |= set(paths or [])
    return out


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: p.parent.name)
def test_every_manifest_path_exists(manifest_path: Path):
    """A dangling path fails silently at run time, which is the worst way."""
    if not manifest_path.exists():
        pytest.skip(f"{manifest_path} absent")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = [p for p in sorted(_paths(manifest)) if not (DOCS / p).exists()]
    assert not missing, f"{manifest_path.name} names files that do not exist: {missing}"


class TestTheStudioCorpusIsNonEngineering:
    MANIFEST = DOCS / "meridian_studio" / "manifest.json"

    def _manifest(self) -> dict:
        assert self.MANIFEST.exists(), (
            "the non-engineering corpus is gone — B14 loses the only thing it "
            "can be demonstrated against")
        return json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_no_declared_domain_is_a_shipped_enum_member(self):
        overlap = set(self._manifest().get("domains", {})) & SHIPPED_DOMAINS
        assert not overlap, (
            f"the studio corpus declares shipped engineering domains {overlap} — "
            "it has drifted back toward the case the harness already served, "
            "which is exactly what docs/smartfactory turned out to be")

    def test_it_covers_every_domain_the_studio_profile_declares(self):
        from autornd.profiles import load_profile

        declared = set(load_profile("studio").domains)
        covered = set(self._manifest().get("domains", {}))
        assert declared <= covered, (
            f"profile declares {sorted(declared - covered)} with no documents — "
            "work in those domains reaches grounding with nothing")

    def test_each_domain_loads_non_empty_context(self):
        from autornd.profiles import DEFAULT_PROFILE, load_profile, set_profile
        from autornd.knowledge.context import load_docs_context

        try:
            set_profile(load_profile("studio"))
            for domain in self._manifest().get("domains", {}):
                ctx = load_docs_context([domain])
                assert ctx.strip(), f"{domain} resolved to empty context"
        finally:
            set_profile(DEFAULT_PROFILE)

    def test_the_smartfactory_corpus_is_still_engineering(self):
        """Not a complaint — a pin. The contrast is the point, and if
        smartfactory ever stops being engineering this file's reasoning about
        which corpus validates what needs re-reading."""
        sf = DOCS / "smartfactory" / "manifest.json"
        if not sf.exists():
            pytest.skip("smartfactory corpus absent")
        domains = set(json.loads(sf.read_text(encoding="utf-8")).get("domains", {}))
        assert domains <= SHIPPED_DOMAINS, (
            "smartfactory now declares a non-shipped domain; it may finally be "
            "usable as a generalization corpus")
