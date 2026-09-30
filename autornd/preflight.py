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


def _base_provider(pin: str) -> str:
    """The provider name behind a call-time specifier.

    Measured 2026-09-30: pins like `inference-net/fp4` never match the bare
    endpoint names (`InferenceNet`) the endpoints route returns, so every
    quant-suffixed pin FAILed preflight while serving live. The `/fp4` is a
    call-time routing specifier, not part of the name; comparison is on the
    bare name with separators and case normalized (the route returns
    `InferenceNet`, configs write `inference-net`).
    """
    return pin.split("/", 1)[0].lower().replace("-", "").replace("_", "")


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


async def run() -> list[Finding]:
    models, pins = _configured(), _pins()
    known = {m["id"] for m in (await _fetch("/models")).get("data", [])}
    endpoints: dict[str, set[str]] = {}
    for model in {models.get(t, "") for t in pins} - {""}:
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
        endpoints[model] = {e.get("provider_name")
                            for e in data.get("endpoints", [])}
    return check(models, pins, known, endpoints)


def main() -> int:
    findings = asyncio.run(run())
    for f in findings:
        print(f)
    bad = [f for f in findings if not f.ok]
    print(f"\n{len(findings) - len(bad)} ok, {len(bad)} failing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
