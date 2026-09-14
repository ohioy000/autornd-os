"""OpenRouter client with model routing per function."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import ValidationError

from autornd.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost: float
    # Why generation stopped, and which upstream served it. Both matter when a
    # reply comes back empty: a reasoning model that spent its whole budget on
    # reasoning returns "length" with no content, which is a very different
    # problem from a provider returning nothing at all.
    finish_reason: str | None = None
    provider: str | None = None
    # Where a search-backed answer came from. Without these a lookup is just
    # another confident assertion, which is the thing it exists to replace.
    citations: list[str] = field(default_factory=list)



def provider_order_for(function: str) -> list[str]:
    """Which providers may serve this tier, highest preference first.

    Per tier, because a pin has to be. Tiers run different models and no
    provider serves them all — a global pin of the triage provider would have
    the search tier asking it for a model it does not host, and with fallbacks
    disabled that is a hard failure rather than a slow one. Shipping a global
    pin and advising people to use it was a defect; this is the fix.

    Syntax, comma separated:

        StreamLake                      every tier prefers StreamLake
        triage:StreamLake,search:       triage pinned, search left free
        triage:StreamLake,Together      triage pinned, everything else Together

    A tier named with an empty value is explicitly unpinned, which is how one
    tier opts out of a global default.
    """
    raw = (settings.openrouter_provider_order or "").strip()
    if not raw:
        return []

    general: list[str] = []
    per_tier: dict[str, list[str]] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            tier, _, provider = entry.partition(":")
            tier, provider = tier.strip().lower(), provider.strip()
            per_tier.setdefault(tier, [])
            if provider:
                per_tier[tier].append(provider)
        else:
            general.append(entry)

    if function.lower() in per_tier:
        return per_tier[function.lower()]
    return general


def _raise_for_status(resp, what: str) -> None:
    """raise_for_status, but keep the half of the error that explains it.

    httpx renders only the status line, and a status code is not a diagnosis. A
    403 here was read as rate limiting and blamed on concurrent runs; the body
    said `Workspace weekly budget of $10.00 exceeded`, which is a different
    problem with a different fix, and it had been discarded at the point of
    raising. One request recovered it. The provider puts the reason in the body
    on every error class it returns — spend ceilings, data-policy refusals,
    unknown models — so the body travels with the exception from here on.
    """
    # Status code rather than `is_success`, so this works against any response
    # object with a status and a body — the test doubles included.
    if resp.status_code < 400:
        return
    detail = ""
    try:
        payload = resp.json()
        detail = (payload.get("error") or {}).get("message") or resp.text
    except Exception:
        detail = resp.text
    raise httpx.HTTPStatusError(
        f"{resp.status_code} from {what}: {str(detail)[:400]}",
        request=resp.request, response=resp,
    )


class BudgetExceeded(RuntimeError):
    """A run asked for more calls or more money than it was allowed."""


def _rejection_note(error: Exception) -> str:
    """Tell the next attempt what the last one got wrong.

    Pydantic's message already names the offending value and lists every
    permitted one, which is more than a re-ask conveys and more than a
    hand-written hint would.
    """
    return (
        "\n\nYour previous reply was rejected and must be corrected:\n"
        f"{error}\n"
        "Return only a JSON object. Use only values the schema permits — do not "
        "invent new field values, and do not add fields that are not in the schema."
    )

class OpenRouterClient:
    """Async client that routes requests to the right model via OpenRouter."""

    FUNCTION_MODELS: dict[str, str] = {
        "triage": settings.model_triage,
        "engineering": settings.model_engineering,
        "architecture": settings.model_architecture,
        "escalation": settings.model_escalation,
        "research": settings.model_research,
        "search": settings.model_search,
        **({"ranker": settings.model_ranker} if settings.model_ranker else {}),
        **({"premium": settings.model_premium} if settings.model_premium else {}),
    }

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url
        self._client: httpx.AsyncClient | None = None

        # Spend and call counts live here, on the one object every request must
        # pass through, because accounting kept anywhere else gets bypassed.
        # It was: the phase runner tallied cost inside run_ai, so research
        # lookups, context expansion and reranking — the three most expensive
        # paths — were free as far as any report was concerned. Eight sectors
        # doing roughly thirty-two search calls self-reported $0.0025.
        self.spend: float = 0.0
        self.calls: int = 0
        self.spend_by_function: dict[str, float] = {}
        self.calls_by_function: dict[str, int] = {}
        # Which upstream actually served each tier. A model id is not a system:
        # the same id served by two providers is two different systems, with
        # different output lengths, latencies, prices and answers. Measured —
        # one triage model moved provider between two runs of the same suite and
        # went from $0.0003 to $0.00001 a call, 70-token replies, and a
        # different risk classification on four sectors. Without this recorded,
        # that looks like a code regression.
        self.providers_by_function: dict[str, set[str]] = {}
        # Optional budgets, used by experiments. Left unset in production: an
        # abort half-way through a real workflow throws away the work done so
        # far, whereas an experiment that runs away is a thing that has already
        # happened here once — forty minutes and $1.28 for an inconclusive run.
        self.call_ceiling: int | None = None
        self.spend_ceiling: float | None = None

    def _account(self, function: str, cost: float,
                 provider: str | None = None) -> None:
        """Record one billable request. Called for every request, no exceptions.

        Budgets are enforced here rather than by the caller, so a ceiling covers
        research lookups and reranking too. A run that exceeds one has already
        paid for the request in hand — this stops the next one.
        """
        self.calls += 1
        self.calls_by_function[function] = self.calls_by_function.get(function, 0) + 1
        if provider:
            self.providers_by_function.setdefault(function, set()).add(provider)
        if cost:
            self.spend += cost
            self.spend_by_function[function] = (
                self.spend_by_function.get(function, 0.0) + cost)

        if self.call_ceiling is not None and self.calls > self.call_ceiling:
            raise BudgetExceeded(
                f"stopped at {self.calls} model calls (ceiling {self.call_ceiling}); "
                f"raise max_calls on the scenario if this is expected. "
                f"By tier: {self.calls_by_function}"
            )
        if self.spend_ceiling is not None and self.spend > self.spend_ceiling:
            raise BudgetExceeded(
                f"stopped at ${self.spend:.4f} (ceiling ${self.spend_ceiling:.4f}). "
                f"By tier: "
                f"{ {k: round(v, 4) for k, v in self.spend_by_function.items()} }"
            )

    def reset_accounting(self) -> None:
        self.spend = 0.0
        self.calls = 0
        self.spend_by_function = {}
        self.calls_by_function = {}
        self.providers_by_function = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/ohioy000/autornd-os",
                    "X-Title": "AutoRnD",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    def get_model(self, function: str) -> str:
        if function == "independent":
            return self.independent_model() or settings.model_engineering
        return self.FUNCTION_MODELS.get(function, settings.model_engineering)

    def independent_model(self) -> str | None:
        """A model for the independent pass, or None if there isn't an honest one.

        The premium tier when configured, otherwise the architecture tier —
        already configured, and a different family from the engineering tier
        that produces the work and its reviews.

        None when the resolution lands on the engineering model, because a
        review by the model under review is not a second opinion. This is not
        hypothetical: `premium` is dropped from FUNCTION_MODELS when unset, and
        the lookup then falls back to engineering, so the "independent" check
        would quietly have been the same model all along.
        """
        candidate = settings.model_premium or settings.model_architecture
        if not candidate or candidate == settings.model_engineering:
            return None
        return candidate

    async def chat(
        self,
        function: str,
        system_prompt: str,
        user_message: str,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 16384,
    ) -> ModelResponse:
        model = self.get_model(function)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        # Ask for real spend rather than inferring it. Providers that ignore
        # this simply omit usage.cost and we fall back to catalogue rates.
        payload["usage"] = {"include": True}

        # Optionally pin who serves the request. A model id alone does not
        # determine behaviour: pinning each of five providers that served one
        # tier gave 28/36, 30/36 and 33/36 on the same suite at 12x price
        # spread. Leave unset for availability; set it when a run has to be
        # reproducible or when quality has been measured.
        order = provider_order_for(function)
        if order:
            payload["provider"] = {"order": order, "allow_fallbacks": False}

        client = await self._get_client()
        resp = await client.post("/chat/completions", json=payload)
        if resp.status_code == 400 and response_format:
            logger.warning(
                "400 with response_format for %s — retrying without it. Body: %s",
                model, resp.text[:300],
            )
            payload.pop("response_format", None)
            resp = await client.post("/chat/completions", json=payload)
        _raise_for_status(resp, "chat/completions")
        data = resp.json()

        choice = data["choices"][0]
        content = choice["message"]["content"] or ""
        finish_reason = choice.get("finish_reason")
        citations = [
            (a.get("url_citation") or {}).get("url", "")
            for a in (choice.get("message", {}).get("annotations") or [])
        ]
        citations = [c for c in citations if c]
        provider = data.get("provider")
        usage = data.get("usage", {})

        if not content.strip():
            logger.warning(
                "Empty content from %s via %s (finish_reason=%s, "
                "completion_tokens=%s, max_tokens=%s)",
                model, provider, finish_reason,
                usage.get("completion_tokens"), max_tokens,
            )
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        reported = (data.get("usage") or {}).get("cost")
        if reported is not None:
            cost = float(reported)
        else:
            cost = self._estimate_cost(model, prompt_tokens, completion_tokens)

        # Every attempt counts, retries included. A retry storm that costs real
        # money should look expensive rather than free.
        self._account(function, cost, provider)

        return ModelResponse(
            content=content,
            model=model,
            finish_reason=finish_reason,
            provider=provider,
            citations=citations,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )

    async def rerank(
        self, model: str, query: str, documents: list[str], top_n: int
    ) -> list[tuple[int, float]]:
        """Score documents against a query with a purpose-built rerank model.

        Returns (original_index, relevance_score) best first. Raises if the
        provider or model does not support the rerank API, which is how the
        caller learns to fall back.
        """
        client = await self._get_client()
        resp = await client.post("/rerank", json={
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        })
        _raise_for_status(resp, "rerank")
        data = resp.json()
        usage = data.get("usage", {}) or {}
        # This cost used to reach a debug log and go no further, so reranking
        # was the one tier that never appeared in any total.
        self._account("ranker", float(usage.get("cost") or 0.0))
        logger.debug(
            "rerank %s: %s docs, %s tokens, cost %s",
            model, len(documents), usage.get("total_tokens"), usage.get("cost"),
        )
        return [
            (int(r["index"]), float(r.get("relevance_score", 0.0)))
            for r in data.get("results", [])
        ]

    async def chat_json(
        self,
        function: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 16384,
        max_retries: int = 3,
        schema: type | None = None,
    ) -> tuple[dict[str, Any], ModelResponse]:
        """Chat and parse the response as JSON. Returns (parsed_dict, response).

        When `schema` is a Pydantic model, the parsed object is validated against
        it inside the retry loop. Syntactically valid JSON of the wrong shape is
        as useless as unparseable text, and a model that produced one usually
        produces a correct one on the next attempt — so both get the same retries.
        """
        import asyncio as _aio

        last_error = None
        # What the previous attempt got wrong, fed back into the next one.
        # Re-asking an identical question is close to hoping: a model that
        # answered `infrastructure_engineer` for a role enum has no reason to
        # answer differently second time. The rejection text already names the
        # offending value and every permitted one, so the cheapest way to spend
        # a retry is to say what was wrong.
        correction = ""
        for attempt in range(max_retries):
            if attempt > 0:
                await _aio.sleep(min(2 ** attempt, 8))
            response = await self.chat(
                function=function,
                system_prompt=system_prompt,
                user_message=user_message + correction,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if not (response.content or "").strip():
                detail = (
                    f"model returned no text (provider={response.provider}, "
                    f"finish_reason={response.finish_reason}"
                )
                if response.finish_reason == "length":
                    detail += (
                        f", completion_tokens={response.completion_tokens} of "
                        f"max_tokens={max_tokens} — a reasoning model can spend "
                        f"its whole budget before emitting an answer; raise "
                        f"max_tokens or use a non-reasoning model for this tier"
                    )
                detail += ")"
                last_error = ValueError(detail)
                logger.warning(
                    "Empty reply (attempt %d/%d) for %s: %s",
                    attempt + 1, max_retries, function, detail,
                )
                continue

            try:
                parsed = self._extract_json(response.content)
                if schema is not None:
                    schema(**parsed)
                return parsed, response
            # ValidationError subclasses ValueError, so it must be caught first
            # or the clause below swallows it — which is what happened, and it
            # logged every schema violation as a parse failure.
            except ValidationError as e:
                last_error = e
                correction = _rejection_note(e)
                logger.warning(
                    "Response did not match %s (attempt %d/%d) for %s: %s",
                    getattr(schema, "__name__", schema), attempt + 1, max_retries,
                    function, e,
                )
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                correction = _rejection_note(e)
                logger.warning(
                    "JSON parse failed (attempt %d/%d) for %s: %s — raw: %s",
                    attempt + 1, max_retries, function, e, (response.content or "")[:300],
                )
        raise last_error

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Find the JSON object in a model's reply.

        Dropping the first line positionally to remove a fence was wrong for
        three shapes seen in practice — a fence with the object on the same
        line (which took the object with it), a closing fence with no newline
        before it, and a sentence of preamble. Each cost a full retry, and one
        of them parsed into a valid-but-meaningless dict rather than failing.
        So: strip fences by pattern, then fall back to the outermost balanced
        object.
        """
        if not text:
            raise ValueError("Empty response content — model returned no text")
        import re

        # Reasoning models put their working in <think> blocks.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        # ```json ... ``` in any of its spellings, including same-line content.
        text = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", text).strip()
        text = re.sub(r"```\s*$", "", text).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            span = OpenRouterClient._outermost_object(text)
            if span is None:
                raise
            parsed = json.loads(span)

        if not isinstance(parsed, dict):
            raise ValueError(
                f"Expected JSON object, got {type(parsed).__name__}: {text[:200]}")
        return parsed

    @staticmethod
    def _outermost_object(text: str) -> str | None:
        """The first balanced {...} span, ignoring braces inside strings."""
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    @staticmethod
    def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate from the provider's own published rates.

        Rates are learned from the model catalogue at startup — AutoRnD hardcodes
        no prices, because it hardcodes no models. An unknown model estimates as
        0.0 rather than inventing a number; a fabricated cost is worse than an
        obviously absent one. Actual spend is read from the provider's usage
        accounting when it reports any, and only falls back to this.
        """
        rates = _model_pricing.get(model)
        if not rates:
            return 0.0
        prompt_rate, completion_rate = rates
        return prompt_tokens * prompt_rate + completion_tokens * completion_rate

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_model_status: dict[str, dict] = {}

# model id -> (prompt rate, completion rate) per token, from the provider catalogue
_model_pricing: dict[str, tuple[float, float]] = {}


async def check_models() -> dict[str, dict]:
    """Validate configured models against OpenRouter's model list."""
    global _model_status
    configured = {
        "triage": settings.model_triage,
        "engineering": settings.model_engineering,
        "architecture": settings.model_architecture,
        "escalation": settings.model_escalation,
    }
    configured["research"] = settings.model_research
    configured["search"] = settings.model_search
    for tier, model_id in (
        ("ranker", settings.model_ranker),
        ("premium", settings.model_premium),
    ):
        if model_id:
            configured[tier] = model_id

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # The catalogue is usually public, and httpx rejects a bare
            # "Bearer " — so only authenticate when there is a key to send.
            # This lets tier ids be validated before a key is configured.
            headers = {}
            if settings.openrouter_api_key.strip():
                headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"
            resp = await client.get(
                f"{settings.openrouter_base_url.rstrip('/')}/models",
                headers=headers,
            )
            _raise_for_status(resp, "models catalogue")
            catalogue = resp.json().get("data", [])
            available_ids = {m["id"] for m in catalogue}
            for m in catalogue:
                pricing = m.get("pricing") or {}
                try:
                    _model_pricing[m["id"]] = (
                        float(pricing.get("prompt") or 0.0),
                        float(pricing.get("completion") or 0.0),
                    )
                except (TypeError, ValueError):
                    continue
    except Exception as exc:
        logger.warning("Could not fetch OpenRouter model list: %s", exc)
        _model_status = {fn: {"model": mid, "available": None} for fn, mid in configured.items()}
        return _model_status

    # The bulk catalogue lists chat models only. Other classes a provider serves
    # — rerankers, embedding models — are absent from it but perfectly valid to
    # configure, so confirm each miss individually before calling it missing.
    misses = {m for m in configured.values() if m and m not in available_ids}
    if misses:
        available_ids |= await _confirm_models(misses)

    status = {}
    for fn, model_id in configured.items():
        status[fn] = {"model": model_id, "available": model_id in available_ids}
    _model_status = status
    return status


async def _confirm_models(model_ids: set[str]) -> set[str]:
    """Check ids one by one against the per-model endpoint.

    A served model returns 200 there whatever its output modality; an unknown id
    returns 404. Anything else (network fault, rate limit) is treated as
    unconfirmed rather than absent — the caller reports that as degraded, which
    is the honest answer when we could not check.
    """
    base = settings.openrouter_base_url.rstrip("/")
    headers = {}
    if settings.openrouter_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"

    confirmed: set[str] = set()

    async def _check(client: httpx.AsyncClient, model_id: str) -> None:
        try:
            resp = await client.get(f"{base}/models/{model_id}/endpoints", headers=headers)
            if resp.status_code == 200:
                confirmed.add(model_id)
        except Exception as exc:
            logger.warning("Could not confirm model %s: %s", model_id, exc)

    async with httpx.AsyncClient(timeout=15.0) as client:
        await asyncio.gather(*[_check(client, m) for m in model_ids])
    return confirmed


def get_model_status() -> dict[str, dict]:
    return _model_status


def rebuild_function_models() -> None:
    OpenRouterClient.FUNCTION_MODELS = {
        "triage": settings.model_triage,
        "engineering": settings.model_engineering,
        "architecture": settings.model_architecture,
        "escalation": settings.model_escalation,
        "research": settings.model_research,
        "search": settings.model_search,
        **({"ranker": settings.model_ranker} if settings.model_ranker else {}),
        **({"premium": settings.model_premium} if settings.model_premium else {}),
    }
