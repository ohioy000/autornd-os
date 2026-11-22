"""A pin is checked, recorded and warned about wherever the harness reports on its configuration.

tests/test_profile_pins.py holds the grammar and the overlay, and tests/test_profile_pin_resolution.py the
sites that read it. This file holds the places that *report*, which is how an owner learns that a pin does
not work before paying for it, and the one gap it closed on the way (preflight did not know the reader tier).

1. Health and the spend guard (check_models) see every profile's pin, the active profile's or not: a profile
   can be switched to at run time, and a pinned model the catalogue cannot rate would run with the guard blind.
2. Preflight checks each pin: the profile it names has a file, its model is in the catalogue, its provider
   serves it, and its endpoint accepts what the harness sends. The calls a pin changes, derived ones included,
   are checked under the label 'profile:function'. It also knows the reader tier now.
3. The eval run's header names the map the run used, with the pins laid over it, the profile and the pins.
4. A role whose tier would silently run on the engineering model is warned about, once, and nothing is refused.
"""

from __future__ import annotations

import logging
import re
from unittest.mock import AsyncMock

import httpx
import pytest

import autornd.preflight as preflight
from autornd import profiles
from autornd.config import PINNABLE_TIERS, ProfilePin, settings
from autornd.preflight import (
    CALL_FUNCTIONS, CHAT_PARAMETERS, NON_PARAMETER_KEYS, OPTIONAL_TIERS, PIN_FUNCTIONS,
    REQUIRED_TIERS, _call_targets, _pin_target, _targets_under, check, check_parameters,
    check_profile_pins, sent_parameters,
)
from autornd.routing.openrouter import OpenRouterClient, check_models
from tests.test_preflight_gate import MODELS, _endpoint, _header, hermetic, sweep  # noqa: F401


def _active(monkeypatch, stem: str) -> None:
    monkeypatch.setattr(profiles, "_active_profile", profiles._active_profile)
    profiles.set_profile(profiles.ProjectProfile(stem=stem))


# ── 1. health and the spend guard ─────────────────────────────────────────────────────────────

def _provider(monkeypatch, listed: dict[str, tuple[str, str]], confirmed: frozenset[str] = frozenset()):
    """A provider whose bulk catalogue lists `listed` (id -> (prompt, completion) price) and whose
    per-model endpoints route answers 200 for the ids in `confirmed` and 404 for any other."""
    import autornd.routing.openrouter as orr

    for name in ("_model_pricing", "_model_per_request", "_model_status"):
        monkeypatch.setattr(orr, name, {})

    async def get(url, **kw):
        request = httpx.Request("GET", url)
        if url.endswith("/endpoints"):
            model = url.split("/models/", 1)[1].removesuffix("/endpoints")
            return httpx.Response(200 if model in confirmed else 404, json={}, request=request)
        data = [{"id": m, "pricing": {"prompt": p, "completion": c}} for m, (p, c) in listed.items()]
        return httpx.Response(200, json={"data": data}, request=request)

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(side_effect=get)
    monkeypatch.setattr(orr.httpx, "AsyncClient", lambda *a, **k: client)
    return orr


TIER_PRICES = {settings.model_triage: ("0.000001", "0.000002"),
               settings.model_engineering: ("0.000001", "0.000002"),
               settings.model_architecture: ("0.000001", "0.000002"),
               settings.model_escalation: ("0.000001", "0.000002"),
               settings.model_research: ("0.000001", "0.000002"),
               settings.model_search: ("0.000001", "0.000002")}


class TestHealthAndTheSpendGuardSeeEveryPin:
    LINE = ("legal:engineering=vendor/legal-model@vendor,"
            "finance:triage=vendor/fin-model:exacto,"
            "legal:judge=vendor/nowhere")

    async def test_every_pin_is_confirmed_under_its_label_the_active_profile_or_not(self, monkeypatch):
        _provider(monkeypatch, {**TIER_PRICES, "vendor/legal-model": ("0.000002", "0.000008"),
                                "vendor/fin-model": ("0.000001", "0.000003")},
                  confirmed=frozenset({"vendor/fin-model:exacto"}))
        monkeypatch.setattr(settings, "profile_models", self.LINE)
        _active(monkeypatch, "general")
        status = await check_models()
        assert status["legal:engineering"] == {"model": "vendor/legal-model", "available": True}
        assert status["finance:triage"] == {"model": "vendor/fin-model:exacto", "available": True}
        assert status["legal:judge"] == {"model": "vendor/nowhere", "available": False}

    async def test_a_pinned_model_is_rated_so_the_spend_guard_is_not_blind(self, monkeypatch):
        orr = _provider(monkeypatch, {**TIER_PRICES, "vendor/legal-model": ("0.000002", "0.000008")})
        monkeypatch.setattr(settings, "profile_models", "legal:engineering=vendor/legal-model@vendor")
        await check_models()
        assert orr._model_pricing["vendor/legal-model"] == (0.000002, 0.000008)

    async def test_a_variant_pin_is_rated_at_its_base_price(self, monkeypatch):
        """The bulk catalogue lists the base entry only; the per-model route confirms the variant
        without a price, so it is rated at the base's (a known price, not an unknown one)."""
        orr = _provider(monkeypatch, {**TIER_PRICES, "vendor/fin-model": ("0.000001", "0.000003")},
                        confirmed=frozenset({"vendor/fin-model:exacto"}))
        monkeypatch.setattr(settings, "profile_models", "finance:triage=vendor/fin-model:exacto")
        await check_models()
        assert orr._model_pricing["vendor/fin-model:exacto"] == (0.000001, 0.000003)

    async def test_a_pin_the_catalogue_does_not_list_shows_in_health_as_unverified(self, monkeypatch):
        from autornd.api.routes import health

        _provider(monkeypatch, dict(TIER_PRICES))
        monkeypatch.setattr(settings, "profile_models", "legal:judge=vendor/nowhere")
        await check_models()
        report = await health()
        assert report["status"] == "degraded"
        assert report["unverified_models"] == ["legal:judge"]

    async def test_no_pins_adds_no_label(self, monkeypatch):
        _provider(monkeypatch, dict(TIER_PRICES))
        monkeypatch.setattr(settings, "profile_models", "")
        status = await check_models()
        assert set(status) == set(REQUIRED_TIERS)
        assert all(":" not in label for label in status)


# ── 2. preflight ──────────────────────────────────────────────────────────────────────────────

class TestPreflightKnowsTheReaderTier:
    GOOD = {t: f"vendor/model-{t}" for t in REQUIRED_TIERS}

    def test_the_tier_lists_agree_with_the_tiers_a_pin_may_name(self):
        """A tier added to config but not to preflight would be pinnable and unchecked."""
        assert set(REQUIRED_TIERS + OPTIONAL_TIERS) == set(PINNABLE_TIERS)
        assert set(CALL_FUNCTIONS) == (set(PINNABLE_TIERS) - {"premium"}) | {"independent"}
        assert set(PIN_FUNCTIONS) == set(CALL_FUNCTIONS)

    def test_a_reader_pin_is_a_tier_this_harness_runs(self):
        models = {**self.GOOD, "reader": "vendor/reader"}
        out = check(models, {"reader": "Quick"}, {"vendor/reader", *self.GOOD.values()},
                    {"vendor/reader": {"Quick"}})
        (finding,) = [f for f in out if f.subject == "pin reader"]
        assert finding.ok is True and "Quick serves vendor/reader" in finding.detail

    def test_a_reader_pin_with_no_reader_model_is_reported_unused_not_failed(self):
        out = check(dict(self.GOOD), {"reader": "Quick"}, set(self.GOOD.values()), {})
        (finding,) = [f for f in out if f.subject == "pin reader"]
        assert finding.ok is True and "MODEL_READER is unset" in finding.detail

    def test_the_pin_target_is_the_readers_model_and_none_when_unset(self):
        assert _pin_target("reader", {"reader": "vendor/reader"}) == ("vendor/reader", "")
        model, note = _pin_target("reader", {})
        assert model is None and "no reader call is made" in note

    def test_the_target_is_left_out_when_unset_as_the_rankers_is(self, hermetic, monkeypatch):
        hermetic("Together", {})
        monkeypatch.setattr(settings, "model_reader", "")
        assert "reader" not in _call_targets()
        monkeypatch.setattr(settings, "model_reader", "vendor/reader")
        assert _call_targets()["reader"] == ("vendor/reader", ["Together"])

    async def test_the_reader_sends_a_plain_chat_and_the_gap_is_named(self, monkeypatch):
        """Preflight lists max_tokens and temperature for the reader. The call also sends `reasoning`,
        which is deliberately not listed: whether to refuse an endpoint that does not list it is a
        ruling not yet made (docs/reviews/2026-11-21-per-profile-pins-and-tuned-prompts.md). This
        fails if the call grows another parameter nobody mirrored."""
        from autornd.knowledge import research

        sent: list[dict] = []

        class Http:
            async def post(self, path, json=None):
                sent.append(json)

                class Response:
                    status_code = 200
                    text = ""

                    @staticmethod
                    def json():
                        return {"choices": [{"message": {"content": '{"passages": []}'},
                                             "finish_reason": "stop"}],
                                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}}

                return Response()

        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=Http()))
        await research._read_chunk(client, "a question", "a chunk")
        (payload,) = sent
        assert set(payload) - NON_PARAMETER_KEYS == set(sent_parameters("reader")) | {"reasoning"}


class TestCheckProfilePins:
    KNOWN = {"vendor/legal-model", "vendor/other"}
    STEMS = ["engineering", "general", "legal"]

    def _one(self, line_pins, endpoints=None, stems=None, known=None):
        return check_profile_pins(line_pins, stems or self.STEMS, known or self.KNOWN,
                                  endpoints if endpoints is not None else {})

    def test_a_pin_for_a_profile_with_no_file_fails_and_names_the_profiles(self):
        (f,) = self._one({"lgeal": {"engineering": ProfilePin("vendor/legal-model", "vendor")}})
        assert f.ok is False and f.subject == "pin lgeal:engineering"
        assert "no profile file 'lgeal.yaml'" in f.detail
        assert "engineering, general, legal" in f.detail

    def test_a_model_the_catalogue_does_not_list_fails(self):
        (f,) = self._one({"legal": {"engineering": ProfilePin("vendor/nowhere", "vendor")}})
        assert f.ok is False and "is not in the provider catalogue" in f.detail

    def test_a_pin_with_no_provider_passes_and_says_who_decides(self):
        (f,) = self._one({"legal": {"engineering": ProfilePin("vendor/legal-model", "")}})
        assert f.ok is True
        assert "the router decides" in f.detail and "OPENROUTER_PROVIDER_ORDER is not applied" in f.detail

    def test_a_provider_that_serves_it_passes(self):
        (f,) = self._one({"legal": {"engineering": ProfilePin("vendor/legal-model", "Vendor")}},
                         endpoints={"vendor/legal-model": {"Vendor"}})
        assert f.ok is True and f.detail == "Vendor serves vendor/legal-model"

    def test_a_provider_that_does_not_serve_it_fails_as_a_404(self):
        (f,) = self._one({"legal": {"engineering": ProfilePin("vendor/legal-model", "Other")}},
                         endpoints={"vendor/legal-model": {"Vendor"}})
        assert f.ok is False and "does not serve vendor/legal-model" in f.detail and "404" in f.detail

    def test_endpoints_that_could_not_be_read_fail_rather_than_pass(self):
        (f,) = self._one({"legal": {"engineering": ProfilePin("vendor/legal-model", "Vendor")}},
                         endpoints={})
        assert f.ok is False and "cannot resolve endpoints" in f.detail

    def test_a_model_absent_from_the_bulk_catalogue_but_with_endpoints_is_real(self):
        """A reranker is not a chat model, so /models does not list it (the 2026-09-22 bug)."""
        (f,) = self._one({"legal": {"ranker": ProfilePin("vendor/reranker", "Fast")}},
                         endpoints={"vendor/reranker": {"Fast"}})
        assert f.ok is True


class TestThePreflightChecksWhatEachPinChanges:
    def test_a_profile_resolves_as_the_client_would_for_it(self, hermetic, monkeypatch):
        hermetic("judge:Alpha,Together", {})
        monkeypatch.setattr(settings, "profile_models", "studio:engineering=vendor/pin-model@vendor")
        studio = _targets_under("studio")
        assert studio["engineering"] == ("vendor/pin-model", ["vendor"])
        # an unset judge falls back to the engineering model the profile reads, with its serving
        assert studio["judge"] == ("vendor/pin-model", ["vendor"])
        assert studio["triage"] == _targets_under("")["triage"]
        assert _targets_under("")["engineering"] == (MODELS["engineering"], ["Together"])

    def test_the_active_profile_is_put_back(self, hermetic, monkeypatch):
        hermetic("", {})
        monkeypatch.setattr(profiles, "_active_profile", profiles._active_profile)
        keep = profiles.load_profile("engineering")
        profiles.set_profile(keep)
        _targets_under("studio")
        assert profiles.get_profile() is keep

    async def _run(self, hermetic, monkeypatch, line, listings, catalogue_extra=()):
        state = hermetic("", listings)
        monkeypatch.setattr(settings, "profile_models", line)

        async def fetch(path: str) -> dict:
            state["fetched"].append(path)
            if path == "/models":
                return {"data": [{"id": m} for m in (*MODELS.values(), *catalogue_extra)]}
            model = path[len("/models/"):-len("/endpoints")]
            return {"data": {"endpoints": state["listings"].get(model, [])}}

        monkeypatch.setattr(preflight, "_fetch", fetch)
        return await preflight.run()

    async def test_run_checks_a_pin_and_the_calls_it_changes_under_the_profiles_label(
            self, hermetic, monkeypatch):
        findings = await self._run(
            hermetic, monkeypatch, "studio:engineering=vendor/pin-model@vendor",
            {"vendor/pin-model": [_endpoint("vendor/fp8")]}, catalogue_extra=("vendor/pin-model",))
        by_subject = {f.subject: f for f in findings}
        assert by_subject["pin studio:engineering"].ok is True
        changed = {s for s in by_subject if s.startswith("params studio:")}
        assert changed == {"params studio:engineering via vendor", "params studio:judge via vendor"}
        assert all(by_subject[s].ok for s in changed)

    async def test_the_global_calls_are_checked_whichever_profile_is_active(self, hermetic, monkeypatch):
        """Run under the profile that has the pin, the global engineering call is still checked, as
        what every other profile reads, and the pinned one only under its label."""
        monkeypatch.setattr(profiles, "_active_profile", profiles._active_profile)
        profiles.set_profile(profiles.load_profile("studio"))
        findings = await self._run(
            hermetic, monkeypatch, "studio:engineering=vendor/pin-model@vendor",
            {"vendor/pin-model": [_endpoint("vendor/fp8")]}, catalogue_extra=("vendor/pin-model",))
        subjects = {f.subject for f in findings}
        assert "params engineering" in subjects, "the global engineering call, unpinned"
        assert "params engineering via vendor" not in subjects
        assert "params studio:engineering via vendor" in subjects

    async def test_a_pin_with_no_provider_on_a_model_the_bulk_catalogue_omits_is_still_real(
            self, hermetic, monkeypatch):
        """A reranker is not a chat model, so /models does not list it, yet its endpoints route
        answers. A pin that names no provider has no order, so nothing else asks for its endpoints."""
        findings = await self._run(
            hermetic, monkeypatch, "studio:ranker=vendor/reranker",
            {"vendor/reranker": [_endpoint("fast/fp8", [])]})
        (finding,) = [f for f in findings if f.subject == "pin studio:ranker"]
        assert finding.ok is True, finding.detail

    def test_a_labelled_search_target_is_judged_as_the_plain_chat_search_is(self):
        """The label 'profile:search' must read as 'search', which sends no JSON mode."""
        targets = {"studio:search": ("vendor/pin-search", ["Vendor"])}
        listings = {"vendor/pin-search": [_endpoint("vendor/fp8", CHAT_PARAMETERS)]}
        (finding,) = check_parameters(targets, listings)
        assert finding.ok is True and finding.subject == "params studio:search via Vendor"

    async def test_run_fails_a_pinned_endpoint_that_lacks_what_is_sent(self, hermetic, monkeypatch):
        findings = await self._run(
            hermetic, monkeypatch, "studio:engineering=vendor/pin-model@vendor",
            {"vendor/pin-model": [_endpoint("vendor/fp8", ["max_tokens", "temperature"])]},
            catalogue_extra=("vendor/pin-model",))
        failing = {f.subject for f in findings if not f.ok}
        assert "params studio:engineering via vendor" in failing

    async def test_run_fails_a_pin_whose_profile_has_no_file(self, hermetic, monkeypatch):
        findings = await self._run(
            hermetic, monkeypatch, "nofile:engineering=vendor/pin-model@vendor",
            {"vendor/pin-model": [_endpoint("vendor/fp8")]}, catalogue_extra=("vendor/pin-model",))
        failing = {f.subject: f for f in findings if not f.ok}
        assert "no profile file 'nofile.yaml'" in failing["pin nofile:engineering"].detail

    async def test_with_no_pins_the_findings_are_the_ones_it_always_made(self, hermetic, monkeypatch):
        findings = await self._run(hermetic, monkeypatch, "", {})
        labelled = [f.subject for f in findings
                    if re.match(r"^(params|temperature|pin) [^ :]+:\S+", f.subject)]
        assert labelled == []
        assert {"params triage", "params engineering", "pin triage"} & {f.subject for f in findings}


# ── 3. the eval run's header ──────────────────────────────────────────────────────────────────

class TestTheRunHeaderNamesWhatServed:
    async def test_with_pins_it_names_the_effective_map_the_profile_and_the_pins(
            self, hermetic, sweep, monkeypatch):
        hermetic("", {})
        line = "studio:engineering=vendor/pin-model@vendor"
        monkeypatch.setattr(settings, "profile_models", line)
        monkeypatch.setattr(profiles, "_active_profile", profiles._active_profile)
        profiles.set_profile(profiles.load_profile("studio"))
        assert await sweep["run"]("--skip-preflight") == 0
        header = _header(sweep["results"])
        assert header["models"]["engineering"] == "vendor/pin-model"
        assert header["models"]["triage"] == MODELS["triage"]
        assert header["profile"] == "studio"
        assert header["profile_models"] == line

    async def test_without_pins_the_map_is_the_global_one(self, hermetic, sweep, monkeypatch):
        hermetic("", {})
        monkeypatch.setattr(settings, "profile_models", "")
        monkeypatch.setattr(profiles, "_active_profile", profiles._active_profile)
        profiles.set_profile(profiles.load_profile("general"))
        assert await sweep["run"]("--skip-preflight") == 0
        header = _header(sweep["results"])
        assert header["models"] == MODELS
        assert header["profile"] == "general" and header["profile_models"] == ""


# ── 4. a role whose tier falls back silently ──────────────────────────────────────────────────

class TestARoleTierThatFallsBackSilentlyIsWarnedAbout:
    @pytest.fixture(autouse=True)
    def _fresh(self, monkeypatch):
        from autornd.specialists import registry

        monkeypatch.setattr(registry, "_warned_tiers", set())
        monkeypatch.setattr(profiles, "_active_profile", profiles._active_profile)
        monkeypatch.setattr(settings, "model_ranker", "")
        monkeypatch.setattr(settings, "model_judge", "")
        monkeypatch.setattr(settings, "profile_models", "")

    ROLES = {"paralegal": {"name": "Paralegal", "tier": "enginering"},      # a typo
             "clerk": {"name": "Clerk", "tier": "ranker"},                   # a tier nothing sets
             "reviewer": {"name": "Reviewer", "tier": "judge"},              # unset judge: documented
             "auditor": {"name": "Auditor", "tier": "independent"},          # derived: no model of its own
             "partner": {"name": "Partner", "tier": "architecture"}}         # fine

    def _build(self, caplog, stem="legal"):
        from autornd.specialists import registry

        profiles.set_profile(profiles.ProjectProfile(stem=stem, roles=dict(self.ROLES)))
        with caplog.at_level(logging.WARNING, logger="autornd.specialists.registry"):
            return registry._profile_templates()

    def test_a_typo_and_a_tier_nothing_sets_are_named(self, caplog):
        self._build(caplog)
        text = caplog.text
        assert "Role 'paralegal' in profile 'legal' names tier 'enginering', which is not a tier" in text
        assert "Role 'clerk' in profile 'legal' names tier 'ranker', which has no model set" in text

    def test_the_judge_tier_and_a_set_tier_are_not(self, caplog):
        self._build(caplog)
        assert "reviewer" not in caplog.text and "partner" not in caplog.text
        assert "auditor" not in caplog.text

    def test_nothing_is_refused_the_role_is_built_with_the_tier_it_names(self, caplog):
        templates = self._build(caplog)
        assert templates["paralegal"]["router_function"] == "enginering"
        assert set(templates) == set(self.ROLES)

    def test_a_reload_does_not_repeat_the_line(self, caplog):
        self._build(caplog)
        self._build(caplog)
        assert caplog.text.count("Role 'paralegal'") == 1

    def test_a_pin_that_gives_the_tier_a_model_needs_no_warning(self, caplog, monkeypatch):
        monkeypatch.setattr(settings, "profile_models", "legal:ranker=vendor/rank-model")
        self._build(caplog)
        assert "Role 'clerk'" not in caplog.text
        assert "Role 'paralegal'" in caplog.text

    def test_no_shipped_profile_names_a_tier_that_falls_back_silently(self, caplog):
        from autornd.specialists import registry

        for stem in profiles.list_profiles():
            profiles.set_profile(profiles.load_profile(stem))
            with caplog.at_level(logging.WARNING, logger="autornd.specialists.registry"):
                registry._profile_templates()
        assert caplog.text == ""


# ── .env.example names every call a pin can be written under ─────────────────────────────────

class TestTheExampleNamesEveryPinnableCall:
    def test_the_sentence_lists_each_function_preflight_accepts(self):
        """It omitted decision and reader while preflight accepted both."""
        from pathlib import Path

        text = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")
        head, _, _ = text.partition("OPENROUTER_PROVIDER_ORDER=")
        sentence = head.rsplit("The names a pin can be written under", 1)[1]
        for name in PIN_FUNCTIONS:
            assert name in sentence, name
