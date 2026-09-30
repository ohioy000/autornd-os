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
        schema: type | None = None,
        function: str | None = None,
    ) -> tuple[dict[str, Any], ModelResponse]:
        # Ruling D35: the graph resolves which tier serves a node (node.tier,
        # honouring tier_when); the specialist only names its default. An
        # explicit function overrides the default — how the judge tier serves
        # nodes whose reviewers are still engineering specialists.
        return await client.chat_json(
            function=function or self.router_function,
            system_prompt=self.system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            schema=schema,
        )
