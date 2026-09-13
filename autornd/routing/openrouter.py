"""OpenRouter client with model routing per function."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
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


class OpenRouterClient:
    """Async client that routes requests to the right model via OpenRouter."""

    FUNCTION_MODELS: dict[str, str] = {
        "triage": settings.model_triage,
        "engineering": settings.model_engineering,
        "architecture": settings.model_architecture,
        "escalation": settings.model_escalation,
        **({"research": settings.model_research} if settings.model_research else {}),
        **({"ranker": settings.model_ranker} if settings.model_ranker else {}),
        **({"premium": settings.model_premium} if settings.model_premium else {}),
    }

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url
        self._client: httpx.AsyncClient | None = None

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
        return self.FUNCTION_MODELS.get(function, settings.model_engineering)

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

        client = await self._get_client()
        resp = await client.post("/chat/completions", json=payload)
        if resp.status_code == 400 and response_format:
            logger.warning(
                "400 with response_format for %s — retrying without it. Body: %s",
                model, resp.text[:300],
            )
            payload.pop("response_format", None)
            resp = await client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        content = choice["message"]["content"] or ""
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        reported = (data.get("usage") or {}).get("cost")
        if reported is not None:
            cost = float(reported)
        else:
            cost = self._estimate_cost(model, prompt_tokens, completion_tokens)

        return ModelResponse(
            content=content,
            model=model,
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
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {}) or {}
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
        for attempt in range(max_retries):
            if attempt > 0:
                await _aio.sleep(min(2 ** attempt, 8))
            response = await self.chat(
                function=function,
                system_prompt=system_prompt,
                user_message=user_message,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                parsed = self._extract_json(response.content)
                if schema is not None:
                    schema(**parsed)
                return parsed, response
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                logger.warning(
                    "JSON parse failed (attempt %d/%d) for %s: %s — raw: %s",
                    attempt + 1, max_retries, function, e, (response.content or "")[:300],
                )
            except ValidationError as e:
                last_error = e
                logger.warning(
                    "Response did not match %s (attempt %d/%d) for %s: %s",
                    getattr(schema, "__name__", schema), attempt + 1, max_retries,
                    function, e,
                )
        raise last_error

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        if not text:
            raise ValueError("Empty response content — model returned no text")
        text = text.strip()
        # Strip <think>...</think> blocks from reasoning models
        import re
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # drop ```json
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected JSON object, got {type(parsed).__name__}: {text[:200]}")
        return parsed

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
    for tier, model_id in (
        ("research", settings.model_research),
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
            resp.raise_for_status()
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
        **({"research": settings.model_research} if settings.model_research else {}),
        **({"ranker": settings.model_ranker} if settings.model_ranker else {}),
        **({"premium": settings.model_premium} if settings.model_premium else {}),
    }
