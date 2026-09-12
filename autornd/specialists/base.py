"""Base specialist class and interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autornd.models.verdicts import SpecialistRole
from autornd.routing.openrouter import ModelResponse, OpenRouterClient


@dataclass
class Specialist:
    role: SpecialistRole
    name: str
    domain: str
    system_prompt: str
    router_function: str  # key into OpenRouterClient.FUNCTION_MODELS

    async def run(
        self,
        client: OpenRouterClient,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 16384,
    ) -> tuple[dict[str, Any], ModelResponse]:
        return await client.chat_json(
            function=self.router_function,
            system_prompt=self.system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
        )
