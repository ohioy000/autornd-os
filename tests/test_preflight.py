"""The free configuration checks, tested against the failures that motivated them.

Each case here is a real run that died on 2026-09-20 after paying for the calls
before it. `check()` is pure so every one can be simulated without a network or
a key (convention 22: an instrument's test simulates the condition it watches).

The last class is the one that matters most. The check that was supposed to
catch a vanished standing pin compared two filtered lists and passed when the
key was absent from both — it could not fail. These assert that each finding
*can*.
"""

from __future__ import annotations

import asyncio

import autornd.preflight as preflight
from autornd.preflight import OPTIONAL_TIERS, REQUIRED_TIERS, check

GOOD = {t: f"vendor/model-{t}" for t in REQUIRED_TIERS}
KNOWN = set(GOOD.values())
NO_PINS: dict[str, str] = {}


def _fail_subjects(findings):
    return {f.subject for f in findings if not f.ok}


class TestModelIds:
    def test_a_clean_configuration_reports_no_failures(self):
        assert not _fail_subjects(check(GOOD, NO_PINS, KNOWN, {}))

    def test_an_unset_tier_fails(self):
        models = {**GOOD, "engineering": ""}
        out = check(models, NO_PINS, KNOWN, {})
        assert "model_engineering" in _fail_subjects(out)
        assert any("unset" in f.detail for f in out if not f.ok)

    def test_an_id_absent_from_the_catalogue_fails(self):
        """Attempt 1 of E1: a `-latest` suffix that exists for no model."""
        models = {**GOOD, "triage": "vendor/model-latest"}
        out = check(models, NO_PINS, KNOWN, {})
        assert "model_triage" in _fail_subjects(out)
        assert any("not in the provider catalogue" in f.detail
                   for f in out if not f.ok)

    def test_every_required_tier_is_examined(self):
        """A guard that skipped a tier would pass on a configuration that cannot run."""
        out = check({}, NO_PINS, KNOWN, {})
        assert _fail_subjects(out) == {f"model_{t}" for t in REQUIRED_TIERS}


class TestPins:
    def test_a_pin_whose_provider_serves_the_model_passes(self):
        pins = {"engineering": "GoodHost"}
        eps = {GOOD["engineering"]: {"GoodHost", "OtherHost"}}
        assert not _fail_subjects(check(GOOD, pins, KNOWN, eps))

    def test_a_pin_whose_provider_does_not_serve_the_model_fails(self):
        """E1 attempt 1's real cause: the id was valid and the pinned provider
        served no endpoint for it. A property of the PAIR, not of either half —
        which is why neither an id check nor a provider check alone finds it."""
        pins = {"architecture": "StreamLakeLike"}
        eps = {GOOD["architecture"]: {"SomeoneElse"}}
        out = check(GOOD, pins, KNOWN, eps)
        assert "pin architecture" in _fail_subjects(out)
        assert any("with fallbacks disabled this is a 404" in f.detail
                   for f in out if not f.ok)

    def test_a_pin_on_a_tier_with_no_model_fails(self):
        out = check({**GOOD, "engineering": ""}, {"engineering": "AnyHost"}, KNOWN, {})
        assert "pin engineering" in _fail_subjects(out)

    def test_unresolvable_endpoints_fail_rather_than_pass_quietly(self):
        """If the endpoint lookup returned nothing, the old habit was to shrug.
        An unknown is not an ok."""
        out = check(GOOD, {"engineering": "AnyHost"}, KNOWN, {})
        assert "pin engineering" in _fail_subjects(out)
        assert any("cannot resolve endpoints" in f.detail for f in out if not f.ok)


class TestTheChecksCanActuallyFail:
    """The lesson of the vanished pin: a check that cannot fail is not a check."""

    def test_the_clean_case_and_the_broken_case_differ(self):
        clean = check(GOOD, {"engineering": "H"}, KNOWN, {GOOD["engineering"]: {"H"}})
        broken = check(GOOD, {"engineering": "H"}, KNOWN, {GOOD["engineering"]: {"J"}})
        assert not _fail_subjects(clean) and _fail_subjects(broken), (
            "the pin check does not distinguish a served pin from an unserved one")

    def test_an_empty_configuration_does_not_read_as_healthy(self):
        """The exact shape of the vacuous check: nothing configured, nothing
        compared, everything 'fine'."""
        out = check({}, {}, set(), {})
        assert _fail_subjects(out), "an empty configuration reported no failures"


class TestOptionalTiers:
    """Both bugs here shipped against a green suite and were found by pointing
    the instrument at a correct configuration — the one case nobody writes.

    Measured 2026-09-22. `ranker` and `premium` are the two tiers the harness
    runs without, so they were left out of the list `_configured()` reads. A
    pin on either then reported **"pinned to X but no model is set"** against
    models that *were* set. The instrument had observed *this tier is not in my
    list* and reported *this tier has no model*: a stronger, different claim,
    and convention 26's exact shape.
    """

    def test_a_pinned_optional_tier_with_a_model_passes(self):
        models = {**GOOD, "ranker": "vendor/reranker", "premium": "vendor/big"}
        out = check(models, {"ranker": "Fireworks", "premium": "Friendli"},
                    KNOWN, {"vendor/reranker": {"Fireworks"},
                            "vendor/big": {"Friendli"}})
        assert not _fail_subjects(out)

    def test_an_unset_optional_tier_is_not_reported_as_a_failure(self):
        """Unset is `ranker`'s normal state and must stay silent — otherwise
        the repair trades a false alarm for a permanent one."""
        out = check({**GOOD, "ranker": "", "premium": ""}, NO_PINS, KNOWN, {})
        assert not _fail_subjects(out)

    def test_a_pin_on_an_optional_tier_with_no_model_still_fails(self):
        """The leniency is bounded: a pin naming a tier that holds no model is
        still a real misconfiguration, optional or not."""
        out = check({**GOOD, "ranker": ""}, {"ranker": "Fireworks"}, KNOWN, {})
        assert "pin ranker" in _fail_subjects(out)

    def test_a_pin_on_an_optional_tier_whose_provider_does_not_serve_it_fails(self):
        out = check({**GOOD, "premium": "vendor/big"}, {"premium": "Friendli"},
                    KNOWN, {"vendor/big": {"Together"}})
        assert "pin premium" in _fail_subjects(out)
        assert any("404" in f.detail for f in out if not f.ok)

    def test_a_pin_on_a_misspelled_tier_says_so_instead_of_blaming_the_model(self):
        """A tier the harness does not run reads exactly like an unset model
        under the old wording. It is a typo, and the finding now says which."""
        out = check(GOOD, {"rankr": "Fireworks"}, KNOWN, {})
        detail = next(f.detail for f in out if f.subject == "pin rankr")
        assert "not a tier this harness runs" in detail
        assert "ranker" in detail        # the listing that makes the typo obvious


class TestAModelAbsentFromTheChatCatalogue:
    """The second bug, and the subtler one. `/models` lists CHAT models, so a
    reranker is legitimately absent from it — `qwen/qwen3-reranker-8b` is not
    there, while `/models/qwen/qwen3-reranker-8b/endpoints` resolves to
    Fireworks perfectly well.

    `run()` skipped endpoint resolution for any model absent from `/models`,
    so a correctly pinned reranker reported "cannot resolve endpoints for
    qwen/qwen3-reranker-8b" — endpoints that were one request away. The
    catalogue's silence about a model was being read as the model not existing.
    """

    def test_endpoints_decide_the_pin_even_when_the_id_is_not_in_the_catalogue(self):
        models = {**GOOD, "ranker": "vendor/reranker"}
        out = check(models, {"ranker": "Fireworks"},
                    KNOWN,                                   # reranker NOT in it
                    {"vendor/reranker": {"Fireworks"}})      # but endpoints resolve
        assert "pin ranker" not in _fail_subjects(out)

    def test_an_unresolvable_model_is_still_reported(self):
        """The bound on the leniency above: absent from the catalogue AND no
        endpoints is a finding, not a shrug."""
        out = check({**GOOD, "ranker": "vendor/ghost"},
                    {"ranker": "Fireworks"}, KNOWN, {})
        assert "pin ranker" in _fail_subjects(out)
        assert any("cannot resolve endpoints" in f.detail
                   for f in out if not f.ok)


class TestTheWiringBeneathCheck:
    """`check()` is pure, which is what makes it testable — and is also why
    testing it alone missed both of 2026-09-22's bugs entirely.

    Neither lived in `check()`. One was in `_configured()`, which built the
    models dict, and one was in `run()`, which built the endpoints dict. Six of
    the seven tests written for those bugs PASSED against the broken code,
    because they handed `check()` a models dict the broken code would never
    have produced. Convention 22 says an instrument's test simulates the
    condition it watches END TO END; a test of the pure core simulates the
    condition the core was already fine with.
    """

    def test_configured_reads_the_optional_tiers_too(self, monkeypatch):
        """The first bug, at its actual site."""
        from autornd.config import settings

        for tier in REQUIRED_TIERS + OPTIONAL_TIERS:
            monkeypatch.setattr(settings, f"model_{tier}",
                                f"vendor/model-{tier}", raising=False)
        configured = preflight._configured()
        assert set(configured) == set(REQUIRED_TIERS + OPTIONAL_TIERS)
        assert configured["ranker"] == "vendor/model-ranker"
        assert configured["premium"] == "vendor/model-premium"

    def test_run_resolves_endpoints_for_a_model_absent_from_the_catalogue(self, monkeypatch):
        """The second bug, at its actual site: a reranker is not a chat model,
        so `/models` does not list it, and skipping on that reported endpoints
        as unresolvable when they were one request away."""
        asked: list[str] = []

        async def fake_fetch(path: str) -> dict:
            asked.append(path)
            if path == "/models":
                return {"data": [{"id": "vendor/chat"}]}       # reranker absent
            return {"data": {"endpoints": [{"provider_name": "Fireworks"}]}}

        monkeypatch.setattr(preflight, "_fetch", fake_fetch)
        monkeypatch.setattr(preflight, "_configured",
                            lambda: {**{t: "vendor/chat" for t in REQUIRED_TIERS},
                                     "ranker": "vendor/reranker", "premium": ""})
        monkeypatch.setattr(preflight, "_pins", lambda: {"ranker": "Fireworks"})

        findings = asyncio.run(preflight.run())
        assert "/models/vendor/reranker/endpoints" in asked
        assert not _fail_subjects(findings)

    def test_run_reports_rather_than_crashes_when_endpoints_cannot_be_fetched(self, monkeypatch):
        """The bound on that leniency. The fetch is now wrapped, and a wrapped
        failure that swallowed the finding would be worse than the bug."""
        async def fake_fetch(path: str) -> dict:
            if path == "/models":
                return {"data": [{"id": "vendor/chat"}]}
            raise RuntimeError("endpoints route is down")

        monkeypatch.setattr(preflight, "_fetch", fake_fetch)
        monkeypatch.setattr(preflight, "_configured",
                            lambda: {**{t: "vendor/chat" for t in REQUIRED_TIERS},
                                     "ranker": "vendor/reranker", "premium": ""})
        monkeypatch.setattr(preflight, "_pins", lambda: {"ranker": "Fireworks"})

        findings = asyncio.run(preflight.run())
        assert "pin ranker" in _fail_subjects(findings)
        assert any("cannot resolve endpoints" in f.detail
                   for f in findings if not f.ok)
