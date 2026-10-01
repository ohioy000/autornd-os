"""Free checks on the live configuration, before a paid run.

**Why this exists.** Four consecutive attempts at one pre-registered experiment
died in the apparatus on 2026-09-20, and every one of them was detectable for
nothing beforehand:

1. a model id that the provider's catalogue does not list (`-latest` suffixes
   that exist for no model) — a 404 on the first call;
2. a model the *pinned provider does not serve*, which is a property of the
   (model, provider) **pair** and not of either alone — a 404 three calls in,
   after paying for the ones before it;
3. a model map that had drifted from the one a pre-registration's pins were
   settled against, so the run was not the contrast it claimed to be;
4. a standing pin that had silently gone absent from `.env`, which no check
   noticed because the check that was supposed to notice compared two filtered
   lists and passed when the key was missing from both.

The fourth is the reason this is a module rather than a habit. **A check that
cannot fail is not a check** — the same lesson as convention 22, arriving from
configuration rather than from tests.

Non-negotiable 2 says free checks run before paid calls. This is that, for the
configuration itself. It names no model and recommends none: it reads what is
configured and asks the provider whether it is real.

Run it with `python -m autornd.preflight`. Nothing here bills.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

REQUIRED_TIERS = ("triage", "engineering", "architecture",
                  "escalation", "research", "search")

# The two tiers the harness runs without. They are not checked for being unset —
# unset is their normal state — but a pin on one is checked exactly like any
# other, because a pinned provider that does not serve the model is a 404
# whether or not the tier was optional.
#
# Measured 2026-09-22: `_configured()` read only REQUIRED_TIERS, so pinning
# `ranker:Fireworks,premium:Friendli` against models that WERE set reported
# "pinned to Fireworks but no model is set" — twice, in red, against a correct
# configuration. The instrument had observed "this tier is not in my list" and
# reported "this tier has no model", which is a stronger and different claim
# (convention 26).
OPTIONAL_TIERS = ("ranker", "premium", "judge")

# The parameters the harness sends, by call path. OpenRouter strips a pinned
# endpoint that does not accept a parameter in the request: "Filter by
# Parameters removed ..." in traces 076, 077, 078 and 082, and on 2026-09-30
# (091 run 2) it removed the escalation pin relace/fp4 and the run died on a
# 404 after paying for eight calls. The endpoints route lists each endpoint's
# supported_parameters, so the check is free.
#
# A hand list, guarded: tests/test_preflight_gate.py builds the real payloads
# through OpenRouterClient.chat_json, .chat and the search lookup and fails
# if these drift from what is actually sent.
CHAT_JSON_PARAMETERS = ("response_format", "max_tokens", "temperature")
CHAT_PARAMETERS = ("max_tokens", "temperature")
# Payload keys that are routing or accounting, not model parameters.
NON_PARAMETER_KEYS = frozenset({"model", "messages", "usage", "provider"})

# Every function name the client is called with, which is what a pin is
# matched on (provider_order_for), not the tier's name in .env. The
# independent pass calls "independent", not "premium" (phases.py).
CALL_FUNCTIONS = ("triage", "engineering", "architecture", "escalation",
                  "research", "search", "judge", "independent", "ranker")


def sent_parameters(function: str) -> tuple[str, ...]:
    """What a call on this function sends. Search is a plain chat (no JSON
    mode); the ranker uses the rerank API, which takes no chat parameters
    (its listwise fallback is best-effort and never fails a run)."""
    if function == "search":
        return CHAT_PARAMETERS
    if function == "ranker":
        return ()
    return CHAT_JSON_PARAMETERS


@dataclass
class Finding:
    ok: bool
    subject: str
    detail: str

    def __str__(self) -> str:
        return f"[{'ok ' if self.ok else 'FAIL'}] {self.subject:34} {self.detail}"


def _configured() -> dict[str, str]:
    from autornd.config import settings
    return {t: getattr(settings, f"model_{t}", "") or ""
            for t in REQUIRED_TIERS + OPTIONAL_TIERS}


def _pins() -> dict[str, str]:
    from autornd.config import settings
    order = settings.openrouter_provider_order or ""
    return {k: v for k, v in
            (p.split(":", 1) for p in order.split(",") if ":" in p) if v}


async def _fetch(path: str) -> dict:
    """One GET against the provider catalogue. Free, and unauthenticated when no
    key is set, so ids can be checked before a key exists — same reasoning as
    `openrouter._refresh_model_status`."""
    import httpx

    from autornd.config import settings
    headers = {}
    if settings.openrouter_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.openrouter_base_url.rstrip('/')}{path}", headers=headers)
        resp.raise_for_status()
        return resp.json()


def _base_model(model: str) -> str:
    """The catalogue id behind a per-request specifier.

    Measured 2026-09-30: `:exacto`-suffixed ids (e.g.
    `moonshotai/kimi-k3:exacto`) are absent from the bulk `/models` listing,
    which carries the plain id only — yet `/models/<exacto-id>/endpoints`
    returns 200 with the same serving list, and InferenceNet served
    kimi-k3-exacto twice that night. The bulk catalogue's silence about a
    suffixed id is not the id not existing; endpoints decide.
    """
    return model.split(":", 1)[0]


def _provider_names(entry: dict) -> set[str]:
    """Every provider identity an endpoint entry carries, normalized.

    Measured 2026-09-30: the endpoints route has (at least) two shapes. Some
    models return a bare `provider_name` (`InferenceNet`); others (Gemini
    3.8 Flash) carry no `provider_name` at all and embed the provider in
    `name` as `"Google AI Studio | google/gemini-3.8-flash-20260902"`.
    Reading only the first shape reported "does not serve" for a pin that
    served live twenty minutes later. Generic rule: collect both, normalize
    both, match on either.
    """
    names: set[str] = set()
    if entry.get("provider_name"):
        names.add(_base_provider(str(entry["provider_name"])))
    name = str(entry.get("name") or "")
    if "|" in name:
        names.add(_base_provider(name.split("|", 1)[0].strip()))
    return {n for n in names if n}


def _base_provider(pin: str) -> str:
    """The provider name behind a call-time specifier.

    Measured 2026-09-30: pins like `inference-net/fp4` never match the bare
    endpoint names (`InferenceNet`) the endpoints route returns, so every
    quant-suffixed pin FAILed preflight while serving live. The `/fp4` is a
    call-time routing specifier, not part of the name; comparison is on the
    bare name with separators, case and whitespace normalized (the route
    returns `InferenceNet` or `Google AI Studio`, configs write
    `inference-net` or `google-ai-studio`).
    """
    return (pin.split("/", 1)[0].lower().replace("-", "").replace("_", "")
            .replace(" ", ""))


def check(models: dict[str, str], pins: dict[str, str],
          known: set[str], endpoints: dict[str, set[str]]) -> list[Finding]:
    """Pure, so the failure modes above can be simulated in a test."""
    known_base = {_base_model(m) for m in known}
    out: list[Finding] = []
    for tier in REQUIRED_TIERS:
        model = models.get(tier, "")
        if not model:
            out.append(Finding(False, f"model_{tier}", "unset — the harness will refuse to start"))
        elif _base_model(model) not in known_base and model not in endpoints:
            out.append(Finding(False, f"model_{tier}", f"{model} is not in the provider catalogue"))
        else:
            out.append(Finding(True, f"model_{tier}", model))
    for tier, provider in pins.items():
        model = models.get(tier, "")
        if not model:
            known_tier = tier in REQUIRED_TIERS + OPTIONAL_TIERS
            out.append(Finding(False, f"pin {tier}", (
                f"pinned to {provider} but no model is set"
                if known_tier else
                f"pinned to {provider} but '{tier}' is not a tier this harness "
                f"runs — check the spelling against "
                f"{', '.join(REQUIRED_TIERS + OPTIONAL_TIERS)}")))
            continue
        serving = endpoints.get(model)
        if serving is None:
            # Endpoints are keyed by exact id; a suffixed id resolves to the
            # same serving list as its base, so fall back to the base before
            # reporting unresolvable.
            serving = endpoints.get(_base_model(model))
        if serving is None:
            out.append(Finding(False, f"pin {tier}", f"cannot resolve endpoints for {model}"))
        elif _base_provider(provider) not in {_base_provider(s) for s in serving}:
            out.append(Finding(
                False, f"pin {tier}",
                f"{provider} does not serve {model} — with fallbacks disabled this is a 404"))
        else:
            out.append(Finding(True, f"pin {tier}", f"{provider} serves {model}"))
    from autornd.routing.openrouter import provider_fallbacks_allowed
    if provider_fallbacks_allowed():
        out.append(Finding(True, "fallbacks", "preferred-first failover open (OPENROUTER_PROVIDER_FALLBACKS)"))
    return out


def _call_targets() -> dict[str, tuple[str, list[str]]]:
    """function -> (model, provider order), resolved exactly as a call is.

    The model comes from the client's own lookup (so an unset judge tier
    resolves to the engineering model, as the judging nodes do), and the
    order from provider_order_for, which reads tier-scoped AND general pins.
    A function the harness cannot reach is left out: the ranker with no
    ranker model, the independent pass with no independent model.
    """
    from autornd.config import settings
    from autornd.routing.openrouter import OpenRouterClient, provider_order_for

    client = OpenRouterClient(api_key="preflight")
    targets: dict[str, tuple[str, list[str]]] = {}
    for function in CALL_FUNCTIONS:
        if function == "ranker":
            model = settings.model_ranker or ""
        elif function == "independent":
            model = client.independent_model() or ""
        else:
            model = client.get_model(function)
        if model:
            targets[function] = (model, provider_order_for(function))
    return targets


def _select(listing: list[dict], pin: str) -> list[dict] | None:
    """The endpoints a pin selects, matched the way the router matches.

    Measured 2026-09-30 (091 run 8): the pin `google` matched no endpoint
    of a model whose endpoint tags were google-ai-studio[/flex|/priority]
    and google-vertex/global[...], and the router removed all of them. It
    matches slugs, not display names (Vertex's provider_name is "Google").
    So: an endpoint whose tag equals the pin; failing that, those whose
    tag's first segment equals it. Case is ignored: pins written Nebius and
    DigitalOcean served live against nebius/fp8 and digitalocean. None when
    the listing carries no tags at all, which leaves the match blind.
    """
    wanted = pin.strip().lower()
    tagged = [(e, str(e.get("tag") or "").strip().lower()) for e in listing]
    if not any(tag for _, tag in tagged):
        return None
    exact = [e for e, tag in tagged if tag == wanted]
    if exact:
        return exact
    return [e for e, tag in tagged if tag.split("/", 1)[0] == wanted]


def check_parameters(targets: dict[str, tuple[str, list[str]]],
                     listings: dict[str, list[dict]]) -> list[Finding]:
    """Pure: does every pinned endpoint accept what the harness sends?

    One finding per (function, pinned provider). An unpinned function is
    reported and does not fail. A listing that cannot say (no listing, no
    tags, no supported_parameters field) is BLIND and fails: no evidence
    must never be reported as no problem (convention 28).
    """
    out: list[Finding] = []
    for function, (model, order) in targets.items():
        sent = sent_parameters(function)
        if not order:
            out.append(Finding(True, f"params {function}",
                               "unpinned — parameter support depends on the "
                               "router's choice"))
            continue
        for provider in order:
            subject = f"params {function} via {provider}"
            if not sent:
                out.append(Finding(True, subject,
                                   "rerank API — sends no chat parameters"))
                continue
            listing = listings.get(model)
            if listing is None:
                out.append(Finding(False, subject, (
                    f"blind — no endpoint listing for {model}, so whether "
                    f"{provider} accepts {', '.join(sent)} is unknown")))
                continue
            selected = _select(listing, provider)
            if selected is None:
                out.append(Finding(False, subject, (
                    f"blind — the listing for {model} carries no endpoint "
                    f"tags to match {provider} against")))
                continue
            if not selected:
                tags = sorted({str(e.get("tag")) for e in listing})
                out.append(Finding(False, subject, (
                    f"{provider} selects no endpoint of {model} (tags: "
                    f"{', '.join(tags)}) — the router removes every candidate")))
                continue
            listed = [e for e in selected if "supported_parameters" in e]
            tags = ", ".join(str(e.get("tag")) for e in selected)
            if not listed:
                out.append(Finding(False, subject, (
                    f"blind — {tags} carries no supported_parameters, so "
                    f"whether it accepts {', '.join(sent)} is unknown")))
                continue
            accepting = [e for e in listed
                         if set(sent) <= set(e.get("supported_parameters") or [])]
            if accepting:
                out.append(Finding(True, subject, (
                    f"{', '.join(str(e.get('tag')) for e in accepting)} "
                    f"accepts {', '.join(sent)}")))
                continue
            missing = sorted(set(sent) - set().union(
                *(set(e.get("supported_parameters") or []) for e in listed)))
            out.append(Finding(False, subject, (
                f"{tags} for {model} does not list {', '.join(missing)}; the "
                f"harness sends {', '.join(sent)} on '{function}' and the "
                f"router strips an endpoint it filters by parameters")))
    return out


async def run() -> list[Finding]:
    models, pins = _configured(), _pins()
    targets = _call_targets()
    known = {m["id"] for m in (await _fetch("/models")).get("data", [])}
    endpoints: dict[str, set[str]] = {}
    listings: dict[str, list[dict]] = {}
    pinned_models = {models.get(t, "") for t in pins} - {""}
    targeted = {model for model, order in targets.values() if order}
    for model in pinned_models | targeted:
        # Ask the endpoints route for every pinned model, INCLUDING ones absent
        # from /models. Measured 2026-09-22: `qwen/qwen3-reranker-8b` is not in
        # /models at all — that route lists chat models, and a reranker is not
        # one — yet /models/qwen/qwen3-reranker-8b/endpoints resolves to
        # Fireworks perfectly well. Skipping on `known` reported "cannot resolve
        # endpoints" for a model whose endpoints were one request away. The
        # catalogue's silence about a model was being read as the model not
        # existing, which is the same shape as the bug above it.
        try:
            data = (await _fetch(f"/models/{model}/endpoints")).get("data", {})
        except Exception:
            continue                      # left unresolved, and reported as such
        listings[model] = list(data.get("endpoints", []))
        if model in pinned_models:
            names: set[str] = set()
            for e in listings[model]:
                names |= _provider_names(e)
            endpoints[model] = names
    return (check(models, pins, known, endpoints)
            + check_parameters(targets, listings))


def main() -> int:
    findings = asyncio.run(run())
    for f in findings:
        print(f)
    bad = [f for f in findings if not f.ok]
    print(f"\n{len(findings) - len(bad)} ok, {len(bad)} failing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
