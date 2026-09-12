"""OpenRouter client with model routing per function."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

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

    FUNCTION_MODELS = {
        "triage": settings.model_triage,
        "engineering": settings.model_engineering,
        "architecture": settings.model_architecture,
        "research": settings.model_research,
        "escalation": settings.model_escalation,
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

        cost = self._estimate_cost(model, prompt_tokens, completion_tokens)

        return ModelResponse(
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )

    async def chat_json(
        self,
        function: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 16384,
        max_retries: int = 3,
    ) -> tuple[dict[str, Any], ModelResponse]:
        """Chat and parse the response as JSON. Returns (parsed_dict, response)."""
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
                return parsed, response
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                logger.warning(
                    "JSON parse failed (attempt %d/%d) for %s: %s — raw: %s",
                    attempt + 1, max_retries, function, e, (response.content or "")[:300],
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
        rates = {
            "deepseek/deepseek-v4-flash": (0.07, 0.14),
            "minimax/minimax-m3": (0.60, 2.40),
            "z-ai/glm-5.3": (1.40, 4.40),
            "google/gemini-2.5-flash": (0.15, 0.60),
            "moonshotai/kimi-k3": (3.00, 12.00),
        }
        input_rate, output_rate = rates.get(model, (1.0, 3.0))
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
