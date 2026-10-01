"""No paid sweep starts without a passing preflight (ARCH-20260930-096).

**What bought this.** `autornd/preflight.py` exists because four attempts at
one experiment died in the apparatus on 2026-09-20, each detectable for free
beforehand, and it was still run only by hand. On the night of 2026-09-29/30,
run 2 (`docs/traces/091-night-20260930T003221Z`) paid for eight calls and
then died on a 404: the router's "Filter by Parameters" removed the
escalation pin `relace/fp4`. Run 8 (`...T023940Z`) died on a 404 before its
first call: the triage pin `google` matched no endpoint slug of its model.
Pins stripped by parameter filtering also ended traces 076, 077, 078 and 082.

**What the gate does.** The eval CLI runs the preflight before any client
exists. A failing finding refuses the sweep with exit code 3 and no results
file. `--skip-preflight` proceeds and the header records the override.
Preflight gains a check that every pinned endpoint lists, in
`supported_parameters`, every parameter the harness sends on that call path.

These tests make no provider call. The catalogue fetch is mocked, the sweep
itself is stubbed, and the owner's `.env` (which config.py loads) is blanked
for every input the gate reads.
"""

from __future__ import annotations

import json
import sys

import pytest

import autornd.evals.cli as cli
import autornd.preflight as preflight
from autornd.config import settings
from autornd.evals.runner import RepeatedReport
from autornd.preflight import (
    CHAT_JSON_PARAMETERS, CHAT_PARAMETERS, NON_PARAMETER_KEYS,
    check_parameters, sent_parameters,
)
from autornd.routing.openrouter import OpenRouterClient

# The six required tiers carry conftest's placeholders.
MODELS = {t: f"test-provider/test-{t}" for t in
          ("triage", "engineering", "architecture", "escalation", "research", "search")}
EVERYTHING = ["response_format", "max_tokens", "temperature", "top_p"]


def _endpoint(tag: str, params: list[str] | None = EVERYTHING) -> dict:
    entry = {"tag": tag, "provider_name": tag.split("/")[0].title()}
    if params is not None:
        entry["supported_parameters"] = list(params)
    return entry


@pytest.fixture
def hermetic(monkeypatch):
    """Every configuration input the gate reads, controlled. Returns a setter
    for the pin string and the per-model endpoint listings."""
    for tier in ("ranker", "premium", "judge"):
        monkeypatch.setattr(settings, f"model_{tier}", "")
    monkeypatch.setattr(settings, "openrouter_provider_fallbacks", "")
    monkeypatch.setattr(OpenRouterClient, "FUNCTION_MODELS", dict(MODELS))
    state = {"listings": {}, "fetched": []}

    async def fake_fetch(path: str) -> dict:
        state["fetched"].append(path)
        if path == "/models":
            return {"data": [{"id": m} for m in MODELS.values()]}
        model = path[len("/models/"):-len("/endpoints")]
        return {"data": {"endpoints": state["listings"].get(model, [])}}

    monkeypatch.setattr(preflight, "_fetch", fake_fetch)

    def configure(order: str, listings: dict[str, list[dict]]) -> dict:
        monkeypatch.setattr(settings, "openrouter_provider_order", order)
        state["listings"] = listings
        return state

    return configure


@pytest.fixture
def sweep(monkeypatch, tmp_path):
    """cli.main with one scenario, the sweep stubbed, clients counted."""
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "one.yaml").write_text("id: one\nrequest: Add retry\n")
    results = tmp_path / "units.jsonl"
    seen = {"sweeps": 0, "clients": 0}

    async def fake_run_repeated(scenarios, spec, client_factory, settings_lookup,
                                repeat=3, **kwargs):
        seen["sweeps"] += 1
        return RepeatedReport(results=[], workflow=spec.name, repeat=repeat)

    class CountingClient(OpenRouterClient):
        def __init__(self, *args, **kwargs):
            seen["clients"] += 1
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(cli, "run_repeated", fake_run_repeated)
    monkeypatch.setattr(cli, "OpenRouterClient", CountingClient)

    async def run(*extra: str) -> int:
        monkeypatch.setattr(sys, "argv", [
            "cli", "--scenarios", str(suite), "--workflow", "engineering-rnd",
            "--repeat", "1", "--results-file", str(results), *extra])
        return await cli.main()

    seen["run"] = run
    seen["results"] = results
    return seen


def _all_ok_listings() -> dict[str, list[dict]]:
    return {MODELS["engineering"]: [_endpoint("nebius/fp8")],
            MODELS["search"]: [_endpoint("perplexity", CHAT_PARAMETERS)]}


def _header(path) -> dict:
    return json.loads(path.read_text().splitlines()[0])


class TestTheGateRefusesBeforeAnyPaidCall:
    """(a) A failing finding refuses the sweep with zero billed calls."""

    async def test_a_failing_finding_refuses_with_no_client_and_no_results(self, hermetic, sweep):
        hermetic("engineering:Nebius", {
            MODELS["engineering"]: [_endpoint("nebius/fp8", ["max_tokens", "temperature"])]})
        code = await sweep["run"]()
        assert code == cli.PREFLIGHT_REFUSED_EXIT == 3
        assert sweep["sweeps"] == 0 and sweep["clients"] == 0
        assert not sweep["results"].exists()

    async def test_a_preflight_that_cannot_run_is_a_refusal(self, hermetic, sweep, monkeypatch):
        """No evidence is never a pass (convention 28)."""
        hermetic("", {})

        async def down(path: str) -> dict:
            raise ConnectionError("catalogue unreachable")

        monkeypatch.setattr(preflight, "_fetch", down)
        assert await sweep["run"]() == 3
        assert sweep["sweeps"] == 0 and sweep["clients"] == 0


class TestTheGateLetsAPassingConfigurationThrough:
    """(b) All ok, so it proceeds; (f) the header carries the findings."""

    async def test_all_ok_proceeds_and_the_header_records_every_finding(self, hermetic, sweep):
        state = hermetic("engineering:Nebius,search:Perplexity", _all_ok_listings())
        assert await sweep["run"]() == 0
        assert sweep["sweeps"] == 1
        record = _header(sweep["results"])["preflight"]
        assert record["ran"] is True and record["override"] is False
        assert record["passed"] is True
        names = {f["name"] for f in record["findings"]}
        assert {"params engineering via Nebius", "params search via Perplexity",
                "params triage", "pin engineering"} <= names
        assert all(set(f) == {"ok", "name", "detail"} for f in record["findings"])
        assert f"/models/{MODELS['engineering']}/endpoints" in state["fetched"]


class TestTheOverrideIsRecorded:
    """(c) --skip-preflight proceeds without running it, and says so."""

    async def test_skip_proceeds_and_the_header_records_the_override(self, hermetic, sweep, monkeypatch):
        hermetic("", {})

        async def must_not_run() -> list:
            raise AssertionError("--skip-preflight still ran the preflight")

        monkeypatch.setattr(preflight, "run", must_not_run)
        assert await sweep["run"]("--skip-preflight") == 0
        assert sweep["sweeps"] == 1
        assert _header(sweep["results"])["preflight"] == {"ran": False, "override": True}


class TestThePinnedEndpointMustAcceptWhatIsSent:
    """(d) A pinned endpoint lacking response_format fails, naming the
    function, the model and the pin; (e) a listing that cannot say is
    BLIND, and blind fails."""

    def test_a_missing_response_format_names_function_model_and_pin(self):
        targets = {"escalation": ("vendor/reasoner", ["relace/fp4"])}
        listings = {"vendor/reasoner": [
            _endpoint("relace/fp4", ["max_tokens", "temperature"]),
            _endpoint("deepinfra/bf16")]}
        (finding,) = check_parameters(targets, listings)
        assert finding.ok is False
        assert finding.subject == "params escalation via relace/fp4"
        assert "vendor/reasoner" in finding.detail
        assert "does not list response_format" in finding.detail

    def test_a_listing_without_supported_parameters_is_blind(self):
        targets = {"triage": ("vendor/fast", ["Nebius"])}
        listings = {"vendor/fast": [_endpoint("nebius/fp8", params=None)]}
        (finding,) = check_parameters(targets, listings)
        assert finding.ok is False and finding.detail.startswith("blind")

    def test_no_listing_at_all_is_blind(self):
        (finding,) = check_parameters({"triage": ("vendor/fast", ["Nebius"])}, {})
        assert finding.ok is False and finding.detail.startswith("blind")

    def test_untagged_listing_is_blind(self):
        listings = {"vendor/fast": [{"provider_name": "Nebius",
                                     "supported_parameters": EVERYTHING}]}
        (finding,) = check_parameters({"triage": ("vendor/fast", ["Nebius"])}, listings)
        assert finding.ok is False and finding.detail.startswith("blind")

    def test_an_unpinned_function_is_reported_and_does_not_fail(self):
        (finding,) = check_parameters({"judge": ("vendor/judge", [])}, {})
        assert finding.ok is True and finding.detail.startswith("unpinned")

    def test_search_is_not_asked_for_json_mode(self):
        """Search is a plain chat. Its pinned serving listed max_tokens and
        temperature but not response_format on 2026-09-30, and it served."""
        targets = {"search": ("vendor/search", ["Perplexity"])}
        listings = {"vendor/search": [_endpoint("perplexity", CHAT_PARAMETERS)]}
        (finding,) = check_parameters(targets, listings)
        assert finding.ok is True

    def test_the_ranker_sends_no_chat_parameters(self):
        targets = {"ranker": ("vendor/reranker", ["Fireworks"])}
        (finding,) = check_parameters(targets, {"vendor/reranker": [_endpoint("fireworks", [])]})
        assert finding.ok is True and "rerank API" in finding.detail


class TestAPinSelectsEndpointsTheWayTheRouterDoes:
    """Matched on endpoint slugs, as 091 run 8 measured, not display names."""

    LISTING = [_endpoint("google-ai-studio/flex"), _endpoint("google-vertex/global/flex"),
               _endpoint("google-ai-studio/priority"), _endpoint("google-vertex/global/priority"),
               _endpoint("google-ai-studio"), _endpoint("google-vertex/global")]

    def test_run_8_the_pin_google_selects_nothing(self):
        """The router removed all six of these for the pin `google`. The old
        pin check passed it, because Vertex's provider_name is "Google"."""
        targets = {"triage": ("vendor/flash", ["google"])}
        (finding,) = check_parameters(targets, {"vendor/flash": self.LISTING})
        assert finding.ok is False and "selects no endpoint" in finding.detail

    def test_an_exact_tag_wins_over_its_tier_rows(self):
        selected = preflight._select(self.LISTING, "google-ai-studio")
        assert [e["tag"] for e in selected] == ["google-ai-studio"]

    def test_a_bare_pin_matches_the_first_segment_ignoring_case(self):
        selected = preflight._select([_endpoint("nebius/fp8")], "Nebius")
        assert [e["tag"] for e in selected] == ["nebius/fp8"]

    def test_a_quantized_pin_must_match_its_tag(self):
        assert preflight._select([_endpoint("xiaomi/fp8")], "xiaomi/fp4") == []


class TestTheTargetsAreWhatTheClientCalls:
    """The check reads (model, pin) the way OpenRouterClient.chat does."""

    def test_judge_falls_back_and_independent_ignores_a_premium_pin(self, hermetic):
        hermetic("judge:Alpha,premium:Beta,Gamma", {})
        targets = preflight._call_targets()
        # Unset judge tier: the judging nodes run on the engineering model.
        assert targets["judge"] == (MODELS["engineering"], ["Alpha"])
        # The independent pass calls function "independent": a premium: pin
        # is never applied to it, and the general pin is.
        assert targets["independent"] == (MODELS["architecture"], ["Gamma"])
        assert targets["triage"] == (MODELS["triage"], ["Gamma"])
        assert "ranker" not in targets          # no ranker model, never called


class TestTheSentListIsWhatTheClientSends:
    """The parameter lists are a hand list, so this builds the real payloads
    and fails if they drift."""

    class _Capture:
        is_closed = False

        def __init__(self):
            self.payloads: list[tuple[str, dict]] = []

        async def post(self, path, json=None):
            self.payloads.append((path, json))
            body = ({"results": [], "usage": {}} if path == "/rerank" else
                    {"choices": [{"message": {"content": '{"ok": true}'},
                                  "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}})

            class Response:
                status_code = 200
                text = ""

                @staticmethod
                def json():
                    return body
            return Response()

    def _client(self):
        client = OpenRouterClient(api_key="test")
        client._client = self._Capture()
        return client

    async def test_chat_json_sends_exactly_the_json_mode_list(self):
        client = self._client()
        await client.chat_json("engineering", "system", "user")
        (_, payload), = client._client.payloads
        assert set(payload) - NON_PARAMETER_KEYS == set(CHAT_JSON_PARAMETERS)
        assert set(sent_parameters("engineering")) == set(CHAT_JSON_PARAMETERS)

    async def test_the_search_lookup_sends_exactly_the_plain_list(self):
        from autornd.knowledge.research import _lookup
        client = self._client()
        await _lookup(client, "request", "question")
        (_, payload), = client._client.payloads
        assert set(payload) - NON_PARAMETER_KEYS == set(sent_parameters("search"))

    async def test_rerank_sends_no_chat_parameter(self):
        client = self._client()
        await client.rerank("vendor/reranker", "query", ["a", "b"], 1)
        (path, payload), = client._client.payloads
        assert path == "/rerank"
        assert not set(payload) & set(CHAT_JSON_PARAMETERS)
        assert sent_parameters("ranker") == ()
