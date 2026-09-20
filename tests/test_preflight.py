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

from autornd.preflight import REQUIRED_TIERS, check

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
